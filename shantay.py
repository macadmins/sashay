#!/usr/bin/python
import os, subprocess
from time import strftime

today = strftime("%Y-%m-%d %H:%M")
bandwidth_lines_list = []
filetype_lines_list = []
excludes = ['egist', 'public', 'peers', 'Opened', 'EC', 'Bad']
filetypes = ['ipa', 'epub', 'pkg']
f = open('/Library/Server/Caching/Logs/Debug.log', 'rU')
# f = open('/private/tmp/Debug.log', 'rU')
for line in f:
    if 'start:' in line:
        bandwidth_lines_list.append(line.split())
    elif not any(x in line for x in excludes):
        if any(x in line for x in filetypes):
            filetype_lines_list.append(line.split())
f.close()
logged_gb_returns = []
logged_gb_origins = []

for each in bandwidth_lines_list:
    logged_gb_returns.append(float(each[5]))
    logged_gb_origins.append(float(each[10]))
daily_total_from_cache = max(logged_gb_returns) - min(logged_gb_returns)
daily_total_from_apple = max(logged_gb_origins) - min(logged_gb_origins)
message = ["Download requests served from cache: ", str(daily_total_from_cache * 1024), " MB", '\n',
    "Amount streamed from Apple: ", str(daily_total_from_apple * 1024), " MB", '\n',
    "Net bandwidth saved: ", str((daily_total_from_cache - daily_total_from_apple) * 1024), " MB"]
# print message
# print filetype_lines_list
subprocess.call('/Applications/Server.app/Contents/ServerRoot/usr/sbin/server postAlert CustomAlert Common subject "Caching Server Data: Today" message "' + ' '.join(message) + '" <<<""', shell=True)