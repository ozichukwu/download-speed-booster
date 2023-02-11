"""
simple download speed booster that works by concurrently downloading
parts of a file and then joining the parts after.

process;
*  input: file url
*  file metadata(name + file type, size) is fetched and saved
*  file size is divided into blocks = number of allowed concurrent connections,
    each part is in-turn downloaded little by little and saved.
*  all blocks are saved to disk and each block has name in the format:
    x.dsb where x is the xth bit (from 0) of the file
*  if a given part downloads fully before some others, it takes up parts of
    the file yet to be downloaded and downloads it
*  if no such part exists, the thread is closed
*  if a given parts encounters error, it restarts from the closest
    point to which it encountered the error
*  after all parts have been downloaded, they are joined as they should be
    and the file is saved
*  file is saved at the same location as script so ensure script is
    executed with appropriate permissions

global vars needed;
** all will be in a dict with keys;

1. blocks[dict of lists]: contain details about part
    of the file that each thread is currently handling...
    e.g {0: [0,1023,20]: thread 0 is downloading bits 0-1023
        & 20 bits has been downloaded, 1: [1024,2047,70]}

2. dl[list of ints]: list of total bits downloaded by each thread
    index 0 for thread 0 and so on

3. total_dl[int]: total bits downloaded
"""


import threading, requests, time, re, pathlib, os


MAX_WORKERS = 16
RANGE_PER_REQ = 1024*1024 #bytes
MIN_INIT_BLOCK_SIZE = 100*1024 #bytes


def _get_filename(response):
    if "content-disposition" in response.headers:
        value = response.headers["content-disposition"]
        return re.findall("filename=\"?(.+)\"?")[0]
    return response.url.split("/")[-1].split("?")[0]

def _get_size(response):
    #download size in bytes
    return int(response.headers["content-length"])

def main(url):
    def work(wid): #worker id
        sess = requests.Session()
        #mask user agent to appear as a browser
        sess.headers.update({"user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36"})

        worker_data_lock.acquire()
        #pointer: download from here
        #end: last part to download
        start, end = worker_data["blocks"][wid][:2]
        ptr = start
        worker_data_lock.release()

        while ptr <= end:
            sess.headers.update({"Range": f"bytes={ptr}-{min(end, ptr+RANGE_PER_REQ-1)}"})

            try:
                response = sess.get(url, allow_redirects=True)
            except Exception as e:
                print(f"Request Error: {e}")
                print("retrying...")
                continue

            if not 200 <= r.status_code <= 299:
                print(f"Thread {wid}, error {response.status_code}, retrying...")
                continue

            #save data
            file = open(f"./{name}/{start}.dsb", "ab")
            file.write(response.content)
            file.close()

            #update variables
            worker_data_lock.acquire()
            worker_data["blocks"][wid][2] += len(response.content)
            worker_data["total_dl"] += len(response.content)
            ptr += len(response.content)
            #just incase some work was taken away
            end = worker_data["blocks"][wid][1]
            worker_data_lock.release()


            #if work is done, find more work from other workers
            if ptr > end:
                worker_data_lock.acquire()

                #find worker that has the most work to do
                #work left = (end - start + 1) - downloaded
                worker_info = max([
                    (k, [*v, v[1] - v[0] + 1 - v[2]])
                    for k,v in worker_data["blocks"].items()
                    
                ], key=lambda k: k[1][3])

                wkr_id = worker_info[0]
                wkr_start, wkr_end, wkr_dl, wkr_left = worker_info[1]

                #if there's work to be taken from here
                #(if work left > RANGE_PER_REQ * 2)
                if wkr_left > RANGE_PER_REQ * 2:
                    #take half the work
                    worker_data["blocks"][wkr_id][1] = \
                                    (wkr_start + wkr_dl + wkr_end)//2
                    
                    worker_data["blocks"][wid] = [
                        (wkr_start + wkr_dl + wkr_end)//2 + 1,
                        wkr_end,
                        0
                    ]
                    start, end = worker_data["blocks"][wid][:2]
                    ptr = start

                worker_data_lock.release()
                    
            

    worker_data = {}
    
    print("Fetching file details")
    r = requests.head(url, allow_redirects=True)
    if not 200 <= r.status_code <= 299:
        raise Exception(f"Request Error: err {r.status_code}")

    worker_data_lock = threading.Lock()
    worker_data["name"] = name = _get_filename(r)
    worker_data["size"] = size = _get_size(r)
    worker_data["total_dl"] = 0
    print(f"File: {name}")
    
    if size < 1024*1024:
        print(f"Size: {size/1024:,.2f}kb")
    else:
        print(f"Size: {size/(1024*1024):,.2f}mb")
    input("ENTER to continue") #**

    #preparing worker blocks
    n_workers = min(MAX_WORKERS, size/MIN_INIT_BLOCK_SIZE)
    data_per_worker = size // n_workers
    worker_data["blocks"] = { i:[i*data_per_worker, data_per_worker*(i+1)-1, 0]
                              for i in range(n_workers)
    }
    worker_data["blocks"][n_workers-1][1] = size

    #directory to store file parts
    pathlib.Path(f"./{name}").mkdir()

    #launching worker threads
    print("Launching worker threads")
    workers = []
    for i in range(n_workers):
        wkr = threading.Thread(target=work, args=(i,))
        workers.append(wkr)
        wkr.start()

    for w in workers:
        w.join()

    #rebuilding file parts
    print("Rebuilding file parts")
    file_parts = sorted(
        (f for f in next(os.walk(f"./{name}/"))[2]
            if re.match("^(?:0|[1-9]\d*)\.dsb$", f)),
        key = lambda k: int(k.split(".")[0])
    )
    main_file = open(f"./{name}/{name}", "ab")
    for fpart_name in file_parts:
        fpart = open(f"./{name}/{fpart_name}", "rb")
        data = fpart.read(1024 * 1024)
        while data:
            main_file.write(data)
            data = fpart.read(1024 * 1024)
        fpart.close()
    main_file.close()

    for fpart_name in file_parts:
        os.remove(f"./{name}/{fpart_name}")
            
    
    

if __name == "__main__":
    url = input("Enter url: ")
    t1 = time.time()
    main(url)
    print(f"took: {time.time() - t1: .3f}s")
