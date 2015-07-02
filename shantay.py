#!/usr/bin/python
import bz2
import datetime
import glob
import optparse
import os
import re
import subprocess
import sys
import tempfile
from CoreFoundation import CFPreferencesCopyAppValue

# #sanity checking - since I'm going through the trouble of pure python bunzip'ing
# plist_path = '/Applications/Server.app/Contents/Info.plist'
# server_app_version = CFPreferencesCopyAppValue('CFBundleShortVersionString', plist_path)
# if not server_app_version:
#     print "Can't find Server.app, are you running this on your Mac server instance?"
#     sys.exit(2)
# elif float(server_app_version) < 4.1:
#     print "Not Version 4.1(+) of Server.app"
#     sys.exit(3)
#
# if os.geteuid() != 0:
#     exit("For the final message send(only), this(currently) needs to be run with 'sudo'.")

def normalize_gbs(mb_or_gb, val_to_operate_on):
    """Used when calculating bandwidth. Takes an index to check, and if MB,
       returns the applicable index divided by 1024 to normalize on GBs"""
    if mb_or_gb == 'MB':
        return float(float(val_to_operate_on) / 1024.0)
    elif mb_or_gb != 'GB':
        return 0.0 # if it's less than 1MB just shove in a placeholder float
    else:
        return float(val_to_operate_on)

def alice(list_to_get_extremes):
    """One pill makes you taller... calculates bandwidth used delta"""
    return max(list_to_get_extremes) - min(list_to_get_extremes)

def gen_mb_or_gb(float):
    """Shows bandwidth in MBs if less than 1GB"""
    if float > 1.0:
        return " ".join([str(round(float, 2)), 'GBs'])
    else:
        return " ".join([str(round(float * 1024), 2), 'MBs'])

#start taking vars from main()
def get_start(how_far_back):
    """Calc reporting period datetimes, returns start datetime as string"""
    delta_object = datetime.timedelta(days=how_far_back)
    start_datetime = str(datetime.datetime.today() - delta_object)[:-3] # lops off UTC's millisecs
    return start_datetime
def join_bzipped_logs(dir_of_logs):
    """Creates tempfile, wildcard searches for all archive logs, then uses bz2 module
       to unpack and append them all to the tempfile. Returns file(list of strings) once populated"""
    #setup tempfile 
    unbzipped_logs = tempfile.mkstemp(suffix='.log',prefix='sashayTemp-')[1]
    # print unbzipped_logs                                                                #debug
    das_bzips = "".join([dir_of_logs, '/Debug-*'])
    bunch_of_bzips = glob.glob(das_bzips)
    opened_masterlog = open(unbzipped_logs, 'w')
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
    return unbzipped_logs

def separate_out_range_and_build_lists(dir_of_logs, unbzipped_logs, start_datetime, to_datetime):
    # todo - this is a bit big and nasty, but good enough for now
    """Opens current debug.log and un-bz'd logs and builds new list of loglines
       that fall within our reporting period. Returns two lists of strings: one for bandwidth,
       other for eventual parsing of filetypes served, device os/model, and ips devices accessed from."""
    our_range_logline_str_list,bandwidth_lines_list,filetype_lines_list,service_restart_timestamps=[],[],[],[]
    try:
        with open(os.path.join(dir_of_logs, 'Debug.log'), 'rU') as current, open(unbzipped_logs, 'rU') as unzipped:
            for f in current, unzipped:
                for line in f:
                    if line[:23] > start_datetime:
                        if line[:23] < to_datetime:
                            our_range_logline_str_list.append(line)
    except IOError as e:
        print 'Operation failed: %s' % e.strerror
        sys.exit(4)
    # currently just resetting start_time if service was restarted to most current occurance
    # and informing with datetime in report (with the proper format to add --through option)
    more_recent_svc_hup = False
    for logline_str in our_range_logline_str_list:
        if 'Registration succeeded.  Resuming server.' in logline_str:
            service_restart_timestamps.append(logline_str[:23])
            more_recent_svc_hup = True
            new_start_datetime = max(service_restart_timestamps)
    # todo - should probably be less repetition below
    excludes = ['egist', 'public', 'peers', 'Opened', 'EC', 'Bad']
    filetypes = ['ipa', 'epub', 'pkg', 'zip']
    if more_recent_svc_hup:
        for logline_str in our_range_logline_str_list:
            if logline_str[:23] > new_start_datetime:
                if 'start:' in logline_str:
                    bandwidth_lines_list.append(logline_str.split())
                elif not any(x in logline_str for x in excludes):
                    if any(x in logline_str for x in filetypes):
                        filetype_lines_list.append(logline_str.split())
    else:
        for logline_str in our_range_logline_str_list:
            if logline_str[:23] > start_datetime:
                if 'start:' in logline_str:
                    bandwidth_lines_list.append(logline_str.split())
                elif not any(x in logline_str for x in excludes):
                    if any(x in logline_str for x in filetypes):
                        filetype_lines_list.append(logline_str.split())
    return bandwidth_lines_list, filetype_lines_list, more_recent_svc_hup, new_start_datetime

def parse_bandwidth(bandwidth_lines_list):
    """ Use indexed fields in log lines to build list of bandwidth transferred, normalizes in GBs,
        then parses deltas for data served from cache or streamed from apple/peers. Returns strings"""
    logged_bytes_from_cache,logged_bytes_from_apple,logged_bytes_from_peers=[],[],[]
    for each in bandwidth_lines_list:
        strip_parens = (each[15])[1:] # silly log line cleanup
        logged_bytes_from_cache.append(normalize_gbs(each[6], each[5]))
        logged_bytes_from_apple.append(normalize_gbs(each[16], strip_parens))
        if not each[19] == '0':
            logged_bytes_from_peers.append(normalize_gbs(each[20], each[19]))
    daily_total_from_cache = alice(logged_bytes_from_cache)
    daily_total_from_apple = alice(logged_bytes_from_apple)
    # check for peers
    if len(logged_bytes_from_peers) > 1:
        if max(logged_bytes_from_peers) > 0.1:
            daily_total_from_peers = alice(logged_bytes_from_peers)
            daily_total_from_apple = daily_total_from_apple - daily_total_from_peers
            peer_amount = 'along with %s from peers' % gen_mb_or_gb(daily_total_from_peers)
    else:
        peer_amount = 'no peer servers detected'
    return daily_total_from_cache, daily_total_from_apple, peer_amount

def get_device_stats(filetype_lines_list):
    """Parses out device stats, returns list motherlode"""
# Example data as of July 2, 2015
# ['2015-06-30', '12:31:04.095', '#eLTtl5KfMlrA', 'Request', 'from', '172.20.202.245:61917', '[itunesstored/1.0', 'iOS/8.3', 'model/iPhone7,1', 'build/12F70', '(6;', 'dt:107)]', 'for', 'http://a1254.phobos.apple.com/us/r1000/038/Purple7/v4/23/23/5e/23235e5d-1a12-f381-c001-60acfe6a56ff/zrh1611131113630130772.D2.pd.ipa']
# ['2015-06-30', '12:32:19.554', '#6d3LgXpVcHAU', 'Request', 'from', '172.18.20.102:52880', '[Software%20Update', '(unknown', 'version)', 'CFNetwork/720.3.13', 'Darwin/14.3.0', '(x86_64)]', 'for', 'http://swcdn.apple.com/content/downloads/58/34/031-25780/u1bqpe4ggzdp86utj2esnxfj4xq5izwwri/FirmwareUpdate.pkg']
# ['2015-06-30', '14:09:00.230', '#sNn+egdFxN7m', 'Request', 'from', '172.18.81.204:60025', '[Software%20Update', '(unknown', 'version)', 'CFNetwork/596.6.3', 'Darwin/12.5.0', '(x86_64)', '(MacBookAir6%2C2)]', 'for', 'http://swcdn.apple.com/content/downloads/15/59/031-21808/qylh17vrdgnipjibo2avj3nbw8y2pzeito/Safari6.2.7MountainLion.pkg']
    IPLog,OSLog,ModelLog,ipas,epubs,pkgs,zips=[],[],[],[],[],[],[]
    for filelog in filetype_lines_list:
        if filelog[5].startswith('172'):
            strip_port = (filelog[5])[:-6]
            IPLog.append(strip_port)
            if filelog[10].startswith('Darwin/12'):
                OSLog.append('Mac OS 10.8.x')
            elif filelog[10].startswith('Darwin/13'):
                OSLog.append('Mac OS 10.9.x')
            elif filelog[10].startswith('Darwin/14'):
                OSLog.append('Mac OS 10.10.x')
            else:
                OSLog.append(filelog[7])
            if len(filelog) == 15:
                ModelLog.append(filelog[12])
            elif filelog[7] == '(unknown':
                ModelLog.append('Unknown Mac')
            else:
                ModelLog.append(filelog[8])
            if (filelog[12]).endswith('ipa'):
                ipas.append(filelog[12])
            elif (filelog[12]).endswith('epub'):
                epubs.append(filelog[12])
            elif (filelog[12]).endswith('pkg'):
                pkgs.append(filelog[12])
            elif (filelog[12]).endswith('zip'):
                zips.append(filelog[12])
    return IPLog,OSLog,ModelLog,ipas,epubs,pkgs,zips

def main():
    p = optparse.OptionParser()
    p.set_usage("""Usage: %prog [options]""")
    p.add_option('--from', '-f', dest='from_datetime',
                 help="""(Integer) Number of days in the past to include in report.
                         Default is 24hrs from current timestamp""")
    p.add_option('--through', '-t', dest='to_datetime',
                 help="""End of date range to report, in format '2015-06-30 12:00:00.000'""")
    p.add_option('--modelvers', '-m', dest='modelvers',
                 help="""Report on iOS device versions and Macs (if logged).""")
    p.add_option('--osrevs', '-r', dest='os_revisions',
                 help="""Report on iOS and Macs OS versions.""")
    p.add_option('--net', '-n', dest='network_ips',
                 help="""Report on total/unique ips and subnets.""")
    p.add_option('--ipa', '-i', dest='ipas',
                 help="""Report on total/unique ipas.""")
    p.add_option('--epub', '-e', dest='epubs',
                 help="""Report on total/unique epubs.""")
    p.add_option('--pkg', '-p', dest='pkgs',
                 help="""Report on total/unique pkgs.""")
    p.add_option('--zip', '-z', dest='zips',
                 help="""Report on total/unique zips (assuming for iOS firmware).""")

    # options, arguments = p.parse_args()
    # if not (options.runOnce or options.runEvery):
    #     print "Please choose a frequency and the path to a folder containing (1 or more) scripts"
    #     p.print_help()
    # dir_of_logs='/Library/Server/Caching/Logs'
    dir_of_logs = '/Users/abanks/Desktop/cashayScratch/Logs'                        #debug
    to_datetime = ''
    start_datetime = get_start(3)
    unbzipped_logs = join_bzipped_logs(dir_of_logs)
    if not to_datetime:
        to_datetime = str(datetime.datetime.today())[:-3]
    (bandwidth_lines_list, filetype_lines_list, more_recent_svc_hup, new_start_datetime) = separate_out_range_and_build_lists(dir_of_logs, unbzipped_logs, start_datetime, to_datetime)
    (daily_total_from_cache, daily_total_from_apple, peer_amount) = parse_bandwidth(bandwidth_lines_list)
    (IPLog,OSLog,ModelLog,ipas,epubs,pkgs,zips) = get_device_stats(filetype_lines_list)

    #build message
    message = ["Download requests served from cache: ", gen_mb_or_gb(daily_total_from_cache), '\n',
        "Amount streamed from Apple (", peer_amount, "): " , gen_mb_or_gb(daily_total_from_apple), '\n',
        "(Potential) Net bandwidth saved (items could have been cached previously): ",
        gen_mb_or_gb(daily_total_from_cache - daily_total_from_apple), '\n', ""]
    if more_recent_svc_hup:
        disclaimer = ['\n', "  * NOTE: Stats are only gathered from last time service was restarted, ", new_start_datetime]
        message += disclaimer
    print(' '.join(message))                                                        #debug
    print OSLog + ModelLog                                                          #debug
    print set(IPLog)
    # subprocess.call('/Applications/Server.app/Contents/ServerRoot/usr/sbin/server postAlert CustomAlert Common subject "Caching Server Data: Today" message "' + ' '.join(message) + '" <<<""', shell=True)

if __name__ == '__main__':
    main()