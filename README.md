# download-speed-booster
Using multiple threads to grab parts of a file from a server supporting the Accept-Range HTTP header

This script is currently in its roughest form and has not been fully tested. Expect bugs in certain situations. Hopefully, I find time to improve on it.

You can use as a module like so;

```python
import dsb

dsb.main(file_url)
```

Or run it directly;

```python
>>> python dsb.py
>>> Enter url: https://myfile.com/file.mkv
>>> ... #stdout prints...
>>>
```

Currently, downloads are saved in the same location as the script so ensure to run with appropriate permissions

ENJOY!
