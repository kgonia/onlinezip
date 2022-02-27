# Onlinezip

Onlinezip is a Python library for reading zip file through network without downloading whole file locally.

You can read one entry or whole zip file entry by entry.

It may be useful when you want to read just few entries or file is really big and you don't want to download it at once. 

## Prerequisites

server with zip file must fulfill two conditions:
- respond to HTTP HEAD request
- allows to read bytes in ranges

Most modern servers supports this.

## Installation

Use the package manager [pip](https://pip.pypa.io/en/stable/) to install onlinezip.

```bash
pip install onlinezip
```

## Usage

OnlineZip juz extending ZipFile. If you know how to use ZiFile class you also know how to use OnlineZip.

To start just pass url to constructor.
```python
from onlinezip.OnlineZip import OnlineZip

zip = OnlineZip('https://public-onlinezip.s3.eu-west-1.amazonaws.com/zip.zip')
```

```python
# returns names of all files in zip
zip.namelist()

# extract file a.txt to local directory
zip.extract('a.txt')

# extract all files
zip.extractall()

# open file
with zip.open('a.txt') as myfile:
    print(myfile.read())
```
Please remember that entries aren't stored neither cache so each time you calls method that read entry you are downloading it.

## Contributing
Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.

Please make sure to update tests as appropriate.

## License
GNU GENERAL PUBLIC LICENSE