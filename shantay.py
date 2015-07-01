#!/usr/bin/python
import bz2
import datetime
import glob
import os
import subprocess
import sys
import tempfile
from CoreFoundation import CFPreferencesCopyAppValue

#gimme some vars
how_far_back = 1
# dir_of_logs='/Library/Server/Caching/Logs'
dir_of_logs = '/Users/abanks/Desktop/cashayScratch/Logs'                        #debug

#time jiggery-pokery
now = str(datetime.datetime.today())[:-3]
delta_object = datetime.timedelta(days=how_far_back)
start_datetime = str(datetime.datetime.today() - delta_object)[:-3] # lops off UTC's millisecs

#data structures for parsing, now and later
bandwidth_lines_list,filetype_lines_list,logged_bytes_from_cache,logged_bytes_from_apple=[],[],[],[]
logged_bytes_from_peers=[]
excludes = ['egist', 'public', 'peers', 'Opened', 'EC', 'Bad']
filetypes = ['ipa', 'epub', 'pkg', 'zip']
#setup tempfile 
master_log = tempfile.mkstemp(suffix='.log',prefix='sashayTemp-')[1]
print master_log                                                                #debug
das_bzips = "".join([dir_of_logs, '/Debug-*'])
bunch_of_bzips = glob.glob(das_bzips)
opened_masterlog = open(master_log, 'w')
#concat each unbz'd log to tempfile
for archived_log in bunch_of_bzips:
    try:
        process_bz = bz2.BZ2File(archived_log)
        opened_masterlog.write(process_bz.read())
    except Exception as e:
        raise e
    finally:
        process_bz.close()
opened_masterlog.close()

more_recent_svc_hup = False

#main loop to populate data structures 
try:
    with open(os.path.join(dir_of_logs, 'Debug.log'), 'rU') as current, open(master_log, 'rU') as unzipped:
        for f in current, unzipped:
            for line in f:
                if line[:23] > start_datetime:
                    if 'start:' in line:
                        bandwidth_lines_list.append(line.split())
                    elif not any(x in line for x in excludes):
                        if any(x in line for x in filetypes):
                            filetype_lines_list.append(line.split())
except IOError as e:
    print 'Operation failed: %s' % e.strerror
    sys.exit(1)

#normalize to GBs
def normalize_gbs(mb_or_gb, val_to_operate_on):
    """take an index to check, and if MB, return applicable index divided by 1024"""
    if mb_or_gb == 'MB':
        return float(float(val_to_operate_on) / 1024.0)
    elif mb_or_gb != 'GB':
        return 0.0 # if it's less than 1MB just shove in a placeholder float
    else:
        return float(val_to_operate_on)

def alice(list_to_get_extremes):
    """one pill makes you taller"""
    return max(list_to_get_extremes) - min(list_to_get_extremes)

for each in bandwidth_lines_list:
    strip_parens = (each[15])[1:] # silly log line cleanup
    logged_bytes_from_cache.append(normalize_gbs(each[6], each[5]))
    logged_bytes_from_apple.append(normalize_gbs(each[16], strip_parens))
    if not each[19] == '0':
        logged_bytes_from_peers.append(normalize_gbs(each[20], each[19]))
daily_total_from_cache = alice(logged_bytes_from_cache)
daily_total_from_apple = alice(logged_bytes_from_apple)

def gen_mb_or_gb(float):
    """based on how big the results of a calc is, either display float and GBs
       or multiply times 1024 and display in MBs"""
    if float > 1.0:
        return " ".join([str(round(float, 2)), 'GBs'])
    else:
        return " ".join([str(round(float * 1024), 2), 'MBs'])

if len(logged_bytes_from_peers) > 1:
    if max(logged_bytes_from_peers) > 0.1:
        daily_total_from_peers = alice(logged_bytes_from_peers)
        daily_total_from_apple = daily_total_from_apple - daily_total_from_peers
        peer_amount = 'along with %s from peers' % gen_mb_or_gb(daily_total_from_peers)
else:
    peer_amount = 'no peer servers detected'

#build message
message = ["Download requests served from cache: ", gen_mb_or_gb(daily_total_from_cache), '\n',
    "Amount streamed from Apple (", peer_amount, "): " , gen_mb_or_gb(daily_total_from_apple), '\n',
    "Net bandwidth saved: ", gen_mb_or_gb(daily_total_from_cache - daily_total_from_apple)]
print(' '.join(message))                                                        #debug
print filetype_lines_list                                                       #debug
# subprocess.call('/Applications/Server.app/Contents/ServerRoot/usr/sbin/server postAlert CustomAlert Common subject "Caching Server Data: Today" message "' + ' '.join(message) + '" <<<""', shell=True)