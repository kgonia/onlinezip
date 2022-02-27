import io
import struct
from copy import copy
from urllib.request import Request
from zipfile import ZipFile, ZipExtFile, sizeFileHeader, BadZipFile, _FH_SIGNATURE, structFileHeader, \
    stringFileHeader, _FH_FILENAME_LENGTH, _FH_EXTRA_FIELD_LENGTH, _FH_GENERAL_PURPOSE_FLAG_BITS, ZipInfo, \
    sizeEndCentDir, structEndArchive, _ECD_OFFSET, _ECD_SIZE, structEndArchive64, _CD64_DIRECTORY_SIZE, \
    _CD64_OFFSET_START_CENTDIR
import urllib.request

EOCD_RECORD_SIZE = sizeEndCentDir
ZIP64_EOCD_RECORD_SIZE = 56
ZIP64_EOCD_LOCATOR_SIZE = 20

MAX_STANDARD_ZIP_SIZE = 4_294_967_295


class HTTPRangeRequestUnsupported(Exception):
    pass


class OnlineZip(ZipFile):
    def __init__(self, url):
        self.url = url
        self._support()
        super().__init__(self._get_central_directory())

    def _support(self):
        req: Request = Request(self.url, method="HEAD")
        resp = urllib.request.urlopen(req)
        self.file_size = int((resp.info()['Content-Length']))
        self.accept_bytes = resp.info()['Accept-Ranges'] == 'bytes'
        if not self.accept_bytes:
            raise HTTPRangeRequestUnsupported("range request is not supported")

    def _get_central_directory(self):
        eocd_record = self._fetch_bytes(self.file_size - EOCD_RECORD_SIZE, EOCD_RECORD_SIZE)
        if self.file_size <= MAX_STANDARD_ZIP_SIZE:
            endrec = struct.unpack(structEndArchive, eocd_record)
            endrec = list(endrec)

            self.cd_start = endrec[_ECD_OFFSET]
            self.cd_size = endrec[_ECD_SIZE]

            # cd_start = self.file_size - cd_size - EOCD_RECORD_SIZE
            central_directory = self._fetch_bytes(self.cd_start, self.cd_size)
            return io.BytesIO(central_directory + eocd_record)
        else:
            zip64_eocd_record = self._fetch_bytes(self.file_size - (
                    EOCD_RECORD_SIZE + ZIP64_EOCD_LOCATOR_SIZE + ZIP64_EOCD_RECORD_SIZE),
                                                  ZIP64_EOCD_RECORD_SIZE)
            zip64_eocd_locator = self._fetch_bytes(self.file_size - (EOCD_RECORD_SIZE + ZIP64_EOCD_LOCATOR_SIZE),
                                                   ZIP64_EOCD_LOCATOR_SIZE)

            endrec = struct.unpack(structEndArchive64, zip64_eocd_record)
            endrec = list(endrec)

            self.cd_start = endrec[_CD64_OFFSET_START_CENTDIR]
            self.cd_size = endrec[_CD64_DIRECTORY_SIZE]

            central_directory = self._fetch_bytes(self.cd_start, self.cd_size)
            return io.BytesIO(central_directory + zip64_eocd_record + zip64_eocd_locator + eocd_record)

    def _fetch_bytes(self, start, length):
        end = start + length - 1
        req = Request(self.url)
        req.add_header('Range', f'bytes={start}-{end}')

        resp = urllib.request.urlopen(req)
        return resp.read()

    def open(self, name, mode="r", pwd=None, *, force_zip64=False):

        # Make sure we have an info object
        if isinstance(name, ZipInfo):
            # 'name' is already an info object
            file_info = name
        else:
            # Get info object for name
            file_info = self.getinfo(name)

        file_info = copy(file_info)

        # offset is calculated wrongly because file info is created from part of file,
        # adding central directory offset give us good value
        # fetching only header
        header_bytes = self._fetch_bytes(file_info.header_offset + self.cd_start, sizeFileHeader)

        try:
            # Skip the file header:
            if len(header_bytes) != sizeFileHeader:
                raise BadZipFile("Truncated file header")
            fheader = struct.unpack(structFileHeader, header_bytes)
            if fheader[_FH_SIGNATURE] != stringFileHeader:
                raise BadZipFile("Bad magic number for file header")

            offset = fheader[_FH_FILENAME_LENGTH]
            if fheader[_FH_EXTRA_FIELD_LENGTH]:
                offset += fheader[_FH_EXTRA_FIELD_LENGTH]

            # now We can fetch rest of bytes, again correction for offset plus header size
            # for size We use compressed size, file name size and extra field size
            file_bytes = self._fetch_bytes(file_info.header_offset + self.cd_start + sizeFileHeader,
                                           file_info.compress_size + offset)

            # little trick
            file_info.header_offset = 0
            # delattr(file_info, 'CRC')

            in_memory_file = io.BytesIO(file_bytes)

            fname = in_memory_file.read(fheader[_FH_FILENAME_LENGTH])
            if fheader[_FH_EXTRA_FIELD_LENGTH]:
                in_memory_file.read(fheader[_FH_EXTRA_FIELD_LENGTH])

            if fheader[_FH_GENERAL_PURPOSE_FLAG_BITS] & 0x800:
                # UTF-8 filename
                fname_str = fname.decode("utf-8")
            else:
                fname_str = fname.decode("cp437")

            if fname_str != file_info.orig_filename:
                raise BadZipFile(
                    'File name in directory %r and header %r differ.'
                    % (file_info.orig_filename, fname))

            # check for encrypted flag & handle password
            is_encrypted = file_info.flag_bits & 0x1
            if is_encrypted:
                if not pwd:
                    pwd = self.pwd
                if not pwd:
                    raise RuntimeError("File %r is encrypted, password "
                                       "required for extraction" % name)
            else:
                pwd = None

            return ZipExtFile(in_memory_file, mode="r", zipinfo=file_info, pwd=pwd)
        except:
            in_memory_file.close()
            raise
