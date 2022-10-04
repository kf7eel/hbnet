#!/usr/bin/env python3
#
###############################################################################
#   Copyright (C) 2016-2019 Cortney T. Buffington, N0MJS <n0mjs@me.com>
#   Copyright (C) 2020-2021 Eric, KF7EEL, <kf7eel@qsl.net>
#
#   This program is free software; you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation; either version 3 of the License, or
#   (at your option) any later version.
#
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#
#   You should have received a copy of the GNU General Public License
#   along with this program; if not, write to the Free Software Foundation,
#   Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301  USA
###############################################################################

'''
This application, in conjuction with it's rule file (rules.py) will
work like a "conference bridge". This is similar to what most hams think of as a
reflector. You define conference bridges and any system joined to that conference
bridge will both receive traffic from, and send traffic to any other system
joined to the same conference bridge. It does not provide end-to-end connectivity
as each end system must individually be joined to a conference bridge (a name
you create in the configuraiton file) to pass traffic.

This program currently only works with group voice calls.
'''

# Python modules we need
import sys
from bitarray import bitarray
from time import time
import importlib.util

# Twisted is pretty important, so I keep it separate
from twisted.internet.protocol import Factory, Protocol
from twisted.protocols.basic import NetstringReceiver
from twisted.internet import reactor, task

# Things we import from the main hblink module
from hblink import HBSYSTEM, OPENBRIDGE, systems, hblink_handler, reportFactory, REPORT_OPCODES, mk_aliases, download_burnlist
from dmr_utils3.utils import bytes_3, int_id, get_alias
from dmr_utils3 import decode, bptc, const
import config
import log
from const import *
from hashlib import sha256

# Stuff for socket reporting
import pickle
# REMOVE LATER from datetime import datetime
# The module needs logging, but handlers, etc. are controlled by the parent
import logging
logger = logging.getLogger(__name__)
import os, ast
import json, requests

# User for different functions that need to be running: APRS, Proxy, etc
import threading

# Hotspot Proxy stuff
from hotspot_proxy_v2 import Proxy

# Used for converting time
from datetime import datetime

import re
from socket import gethostbyname

from setproctitle import setproctitle

import copy
from pathlib import Path
import sys





# Does anybody read this stuff? There's a PEP somewhere that says I should do this.
__author__     = 'Cortney T. Buffington, N0MJS, Eric Craw, KF7EEL, kf7eel@qsl.net'
__copyright__  = 'Copyright (c) 2016-2019 Cortney T. Buffington, N0MJS and the K0USY Group, Copyright (c) 2020-2021, Eric Craw, KF7EEL'
__credits__    = 'Colin Durbridge, G4EML, Steve Zingman, N4IRS; Mike Zingman, N4IRR; Jonathan Naylor, G4KLX; Hans Barthen, DL5DI; Torsten Shultze, DG1HT'
__license__    = 'GNU GPLv3'
__maintainer__ = 'Eric Craw, KF7EEL'
__email__      = 'kf7eel@qsl.net'

##import os, ast

### Function to download rules
##def update_tg(CONFIG, mode, dmr_id, data):
##    user_man_url = CONFIG['WEB_SERVICE']['URL']
##    shared_secret = str(sha256(CONFIG['WEB_SERVICE']['SHARED_SECRET'].encode()).hexdigest())
##    update_srv = {
##    'update_tg':CONFIG['WEB_SERVICE']['THIS_SERVER_NAME'],
##    'secret':shared_secret,
##    'dmr_id': dmr_id,
####    'ts1': data['ts1'],
####    'ts2': data['ts2'],
##    'mode': mode,
##    'data': data
##    }
####    print(rules_check)
##    json_object = json.dumps(update_srv, indent = 4)
##    
##    try:
##        req = requests.post(user_man_url, data=json_object, headers={'Content-Type': 'application/json'})
####        resp = json.loads(req.text)
####        print(resp)
####        return resp['rules']
##    except requests.ConnectionError:
##        logger.error('Config server unreachable, defaulting to local config')
####        return config.build_config(cli_file)


def send_unit_table(CONFIG, _data):
    user_man_url = CONFIG['WEB_SERVICE']['URL']
    shared_secret = str(sha256(CONFIG['WEB_SERVICE']['SHARED_SECRET'].encode()).hexdigest())
    sms_data = {
    'server': CONFIG['WEB_SERVICE']['THIS_SERVER_NAME'],
    'mode':'unit_table',
    'secret':shared_secret,
    'data': str(_data),
    }
    json_object = json.dumps(sms_data, indent = 4)
    
    try:
        req = requests.post(user_man_url, data=json_object, headers={'Content-Type': 'application/json'})
##        resp = json.loads(req.text)
##        print(resp)
##        return resp['rules']
    except requests.ConnectionError:
        logger.error('Config server unreachable')

def ping(CONFIG, _bridge_data):
    user_man_url = CONFIG['WEB_SERVICE']['URL']
    shared_secret = str(sha256(CONFIG['WEB_SERVICE']['SHARED_SECRET'].encode()).hexdigest())
    ping_data = {
    'server': CONFIG['WEB_SERVICE']['THIS_SERVER_NAME'],
    'mode': 'ping',
    'secret':shared_secret,
    'bridge_data': str(_bridge_data),
    'user_systems': str(user_systems())
    }
##    print(rules_check)
    json_object = json.dumps(ping_data, indent = 4)
    
    try:
        req = requests.post(user_man_url, data=json_object, headers={'Content-Type': 'application/json'})
        resp = json.loads(req.text)
        logger.debug(resp)
        for c in resp['commands']:
            if c == 'restart':
                print('restart')
                print(sys.argv)
                os.execv(__file__, sys.argv)
            elif 'on:' in c or 'off:' in c:
                
                parse = re.sub('on:|off:','', c)
                data_list = parse.split(',')
                iBRIDGES = copy.deepcopy(BRIDGES)
##                print(parse)
##                print(BRIDGES[data_list[0]])
##                print(BRIDGES[data_list[0]])
##                print(type(BRIDGES[data_list[0]]))
##                print(BRIDGES[data_list[0]][1])
                n = 0
                for r in iBRIDGES[data_list[0]]:
##                    print(r['SYSTEM'])
                    if r['SYSTEM'] == data_list[1]:
##                        print(n)
##                        print(r['SYSTEM'])
##                        print(BRIDGES[data_list[0]][n]['SYSTEM'])
##                        print(BRIDGES[data_list[0]][n]['ACTIVE'])
                        if 'on:' in c:
                            BRIDGES[data_list[0]][n]['ACTIVE'] = True
                            BRIDGES[data_list[0]][n]['TIMER'] = time() + iBRIDGES[data_list[0]][n]['TIMEOUT']
                        if 'off:' in c:
                            BRIDGES[data_list[0]][n]['ACTIVE'] = False
                        print(BRIDGES[data_list[0]][n]['ACTIVE'])
                    n = n + 1
            else:
                print(c)
           
    ##        return resp['rules']
    except requests.ConnectionError:
        logger.error('Config server unreachable')
##        return config.build_config(cli_file)


# Function to download rules
def download_rules(L_CONFIG_FILE, cli_file):
    user_man_url = L_CONFIG_FILE['WEB_SERVICE']['URL']
    shared_secret = str(sha256(L_CONFIG_FILE['WEB_SERVICE']['SHARED_SECRET'].encode()).hexdigest())
    rules_check = {
    'server': L_CONFIG_FILE['WEB_SERVICE']['THIS_SERVER_NAME'],
    'mode': 'get_rules',
    'secret':shared_secret
    }
##    print(rules_check)
    json_object = json.dumps(rules_check, indent = 4)
    
    try:
        req = requests.post(user_man_url, data=json_object, headers={'Content-Type': 'application/json'})
        resp = json.loads(req.text)
##        print(resp)
        return resp['rules']
    except requests.ConnectionError:
        logger.error('Config server unreachable, defaulting to local config')
        return config.build_config(cli_file)


# Function to download config
def download_config(L_CONFIG_FILE, cli_file):
    user_man_url = L_CONFIG_FILE['WEB_SERVICE']['URL']
    shared_secret = str(sha256(L_CONFIG_FILE['WEB_SERVICE']['SHARED_SECRET'].encode()).hexdigest())
    config_check = {
    'server': L_CONFIG_FILE['WEB_SERVICE']['THIS_SERVER_NAME'],
    'mode': 'get_config',
    'secret':shared_secret
    }
    json_object = json.dumps(config_check, indent = 4)
    
    try:
        req = requests.post(user_man_url, data=json_object, headers={'Content-Type': 'application/json'})
        resp = json.loads(req.text)
        iterate_config = resp['peers'].copy()
        corrected_config = resp['config'].copy()
        corrected_config['SYSTEMS'] = {}
        corrected_config['LOGGER'] = {}
        iterate_config.update(resp['masters'].copy())
        corrected_config['SYSTEMS'].update(iterate_config)
        corrected_config['LOGGER'].update(L_CONFIG_FILE['LOGGER'])
##        corrected_config['WEB_SERVICE'].update(resp['config']['WEB_SERVICE'])
        corrected_config['WEB_SERVICE'] = {}
        corrected_config['WEB_SERVICE']['THIS_SERVER_NAME'] = L_CONFIG_FILE['WEB_SERVICE']['THIS_SERVER_NAME']
        corrected_config['WEB_SERVICE']['URL'] = L_CONFIG_FILE['WEB_SERVICE']['URL']
        corrected_config['WEB_SERVICE']['SHARED_SECRET'] = L_CONFIG_FILE['WEB_SERVICE']['SHARED_SECRET']
        corrected_config['WEB_SERVICE']['REMOTE_CONFIG_ENABLED'] = L_CONFIG_FILE['WEB_SERVICE']['REMOTE_CONFIG_ENABLED']
        corrected_config['WEB_SERVICE'].update(resp['config']['WEB_SERVICE'])
        corrected_config['GLOBAL']['TG1_ACL'] = config.acl_build(corrected_config['GLOBAL']['TG1_ACL'], 4294967295)
        corrected_config['GLOBAL']['TG2_ACL'] = config.acl_build(corrected_config['GLOBAL']['TG2_ACL'], 4294967295)
        corrected_config['GLOBAL']['REG_ACL'] = config.acl_build(corrected_config['GLOBAL']['REG_ACL'], 4294967295)
        corrected_config['GLOBAL']['SUB_ACL'] = config.acl_build(corrected_config['GLOBAL']['SUB_ACL'], 4294967295)
##        corrected_config['SYSTEMS'] = {}
        for i in iterate_config:
##            corrected_config['SYSTEMS'][i]['GROUP_HANGTIME'] = int(iterate_config[i]['GROUP_HANGTIME'])
##            corrected_config['SYSTEMS'][i] = {}
##            print(iterate_config[i])
            if iterate_config[i]['MODE'] == 'MASTER' or iterate_config[i]['MODE'] == 'PROXY' or iterate_config[i]['MODE'] == 'OPENBRIDGE':
##                print(iterate_config[i])
                corrected_config['SYSTEMS'][i]['TG1_ACL'] = config.acl_build(iterate_config[i]['TG1_ACL'], 4294967295)
                corrected_config['SYSTEMS'][i]['TG2_ACL'] = config.acl_build(iterate_config[i]['TG2_ACL'], 4294967295)
                corrected_config['SYSTEMS'][i]['PASSPHRASE'] = bytes(iterate_config[i]['PASSPHRASE'], 'utf-8')
                if iterate_config[i]['MODE'] == 'OPENBRIDGE':
##                    corrected_config['SYSTEMS'][i]['NETWORK_ID'] = int(iterate_config[i]['NETWORK_ID']).to_bytes(4, 'big')
                    corrected_config['SYSTEMS'][i]['NETWORK_ID'] = int(iterate_config[i]['NETWORK_ID']).to_bytes(4, 'big')
                    corrected_config['SYSTEMS'][i]['PASSPHRASE'] = (iterate_config[i]['PASSPHRASE'] + b'\x00' * 30)[:20] #bytes(re.sub('', "b'|'", str(iterate_config[i]['PASSPHRASE'])).ljust(20, '\x00')[:20], 'utf-8') #bytes(iterate_config[i]['PASSPHRASE'].ljust(20,'\x00')[:20], 'utf-8')
                    corrected_config['SYSTEMS'][i]['BOTH_SLOTS'] = iterate_config[i]['BOTH_SLOTS']
                    corrected_config['SYSTEMS'][i]['TARGET_SOCK'] = (gethostbyname(iterate_config[i]['TARGET_IP']), iterate_config[i]['TARGET_PORT'])
                    corrected_config['SYSTEMS'][i]['ENCRYPTION_KEY'] = bytes(iterate_config[i]['ENCRYPTION_KEY'], 'utf-8')
                    corrected_config['SYSTEMS'][i]['ENCRYPT_ALL_TRAFFIC'] = iterate_config[i]['ENCRYPT_ALL_TRAFFIC']
                    

            if iterate_config[i]['MODE'] == 'PEER' or iterate_config[i]['MODE'] == 'XLXPEER':
##                print(iterate_config[i])
                corrected_config['SYSTEMS'][i]['GROUP_HANGTIME'] = int(iterate_config[i]['GROUP_HANGTIME'])
                corrected_config['SYSTEMS'][i]['RADIO_ID'] = int(iterate_config[i]['RADIO_ID']).to_bytes(4, 'big')
                corrected_config['SYSTEMS'][i]['TG1_ACL'] = config.acl_build(iterate_config[i]['TG1_ACL'], 4294967295)
                corrected_config['SYSTEMS'][i]['TG2_ACL'] = config.acl_build(iterate_config[i]['TG2_ACL'], 4294967295)
##                corrected_config['SYSTEMS'][i]['SUB_ACL'] = config.acl_build(iterate_config[i]['SUB_ACL'], 4294967295)
                corrected_config['SYSTEMS'][i]['MASTER_SOCKADDR'] = tuple(iterate_config[i]['MASTER_SOCKADDR'])
                corrected_config['SYSTEMS'][i]['SOCK_ADDR'] = tuple(iterate_config[i]['SOCK_ADDR'])
                corrected_config['SYSTEMS'][i]['PASSPHRASE'] = bytes((iterate_config[i]['PASSPHRASE']), 'utf-8')
                corrected_config['SYSTEMS'][i]['CALLSIGN'] = bytes((iterate_config[i]['CALLSIGN']).ljust(8)[:8], 'utf-8')
                corrected_config['SYSTEMS'][i]['RX_FREQ'] = bytes((iterate_config[i]['RX_FREQ']).ljust(9)[:9], 'utf-8')
                corrected_config['SYSTEMS'][i]['TX_FREQ'] = bytes((iterate_config[i]['TX_FREQ']).ljust(9)[:9], 'utf-8')
                corrected_config['SYSTEMS'][i]['TX_POWER'] = bytes((iterate_config[i]['TX_POWER']).rjust(2,'0'), 'utf-8')
                corrected_config['SYSTEMS'][i]['COLORCODE'] = bytes((iterate_config[i]['COLORCODE']).rjust(2,'0'), 'utf-8')
                corrected_config['SYSTEMS'][i]['LATITUDE'] = bytes((iterate_config[i]['LATITUDE']).ljust(8)[:8], 'utf-8')
                corrected_config['SYSTEMS'][i]['LONGITUDE'] = bytes((iterate_config[i]['LONGITUDE']).ljust(9)[:9], 'utf-8')
                corrected_config['SYSTEMS'][i]['HEIGHT'] = bytes((iterate_config[i]['HEIGHT']).rjust(3,'0'), 'utf-8')
                corrected_config['SYSTEMS'][i]['LOCATION'] = bytes((iterate_config[i]['LOCATION']).ljust(20)[:20], 'utf-8')
                corrected_config['SYSTEMS'][i]['DESCRIPTION'] = bytes((iterate_config[i]['DESCRIPTION']).ljust(19)[:19], 'utf-8')
                corrected_config['SYSTEMS'][i]['SLOTS'] = bytes((iterate_config[i]['SLOTS']), 'utf-8')
                corrected_config['SYSTEMS'][i]['URL'] = bytes((iterate_config[i]['URL']).ljust(124)[:124], 'utf-8')
                corrected_config['SYSTEMS'][i]['SOFTWARE_ID'] = bytes(('Development').ljust(40)[:40], 'utf-8')#bytes(('HBNet V1.0').ljust(40)[:40], 'utf-8')
                corrected_config['SYSTEMS'][i]['PACKAGE_ID'] = bytes(('HBNet').ljust(40)[:40], 'utf-8')
                corrected_config['SYSTEMS'][i]['OPTIONS'] = b''.join([b'Type=HBNet;', bytes(iterate_config[i]['OPTIONS'], 'utf-8')])



            
            if iterate_config[i]['MODE'] == 'PEER':
                    corrected_config['SYSTEMS'][i].update({'STATS':{
                        'CONNECTION': 'NO',             # NO, RTPL_SENT, AUTHENTICATED, CONFIG-SENT, YES 
                        'CONNECTED': None,
                        'PINGS_SENT': 0,
                        'PINGS_ACKD': 0,
                        'NUM_OUTSTANDING': 0,
                        'PING_OUTSTANDING': False,
                        'LAST_PING_TX_TIME': 0,
                        'LAST_PING_ACK_TIME': 0,
                    }})
            if iterate_config[i]['MODE'] == 'XLXPEER':
                corrected_config['SYSTEMS'][i].update({'XLXSTATS': {
                    'CONNECTION': 'NO',             # NO, RTPL_SENT, AUTHENTICATED, CONFIG-SENT, YES 
                    'CONNECTED': None,
                    'PINGS_SENT': 0,
                    'PINGS_ACKD': 0,
                    'NUM_OUTSTANDING': 0,
                    'PING_OUTSTANDING': False,
                    'LAST_PING_TX_TIME': 0,
                    'LAST_PING_ACK_TIME': 0,
                }})
            corrected_config['SYSTEMS'][i]['USE_ACL'] = iterate_config[i]['USE_ACL']
            corrected_config['SYSTEMS'][i]['SUB_ACL'] = config.acl_build(iterate_config[i]['SUB_ACL'], 16776415)
        return corrected_config
    # For exception, write blank dict
    except Exception as e:
        logger.error('Config server unreachable or other error')
        logger.error(e)
        return config.build_config(cli_file)

    
# From hotspot_proxy2, FreeDMR
def hotspot_proxy(listen_port, port_start, port_stop):
##    Master = "127.0.0.1"
##    ListenPort = listen_port
##    DestportStart = port_start
##    DestPortEnd = port_stop
##    Timeout = 30
##    Stats = True
##    Debug = False
##    BlackList = [1234567]
##    
##   
##    CONNTRACK = {}
##
##    for port in range(DestportStart,DestPortEnd+1,1):
##        CONNTRACK[port] = False
##    
##
##    reactor.listenUDP(ListenPort,Proxy(Master,ListenPort,CONNTRACK,BlackList,Timeout,Debug,DestportStart,DestPortEnd))
##
##    def loopingErrHandle(failure):
##        logger.error('(GLOBAL) STOPPING REACTOR TO AVOID MEMORY LEAK: Unhandled error innowtimed loop.\n {}'.format(failure))
##        reactor.stop()
##        
##    def stats():        
##        count = 0
##        nowtime = time()
##        for port in CONNTRACK:
##            if CONNTRACK[port]:
##                count = count+1
##                
##        totalPorts = DestPortEnd - DestportStart
##        freePorts = totalPorts - count
##        
##        logger.info("{} ports out of {} in use ({} free)".format(count,totalPorts,freePorts))
##
##
##        
##    if Stats == True:
##        stats_task = task.LoopingCall(stats)
##        statsa = stats_task.start(30)
##        statsa.addErrback(loopingErrHandle)

    Master = "127.0.0.1"
    ListenPort = listen_port
    # '' = all IPv4, '::' = all IPv4 and IPv6 (Dual Stack)
    ListenIP = ''
    DestportStart = port_start
    DestPortEnd = port_stop
    Timeout = 30
    Stats = False
    Debug = False
    ClientInfo = True
    BlackList = [1234567]
    
#*******************
    
    
    #Set process title early
    setproctitle(__file__)
    
    #If IPv6 is enabled by enivornment variable...
    if ListenIP == '' and 'FDPROXY_IPV6' in os.environ and bool(os.environ['FDPROXY_IPV6']):
        ListenIP = '::'
        
    #Override static config from Environment
    if 'FDPROXY_STATS' in os.environ:
        Stats = bool(os.environ['FDPROXY_STATS'])
    if 'FDPROXY_DEBUG' in os.environ:
        Debug = bool(os.environ['FDPROXY_DEBUG'])
    if 'FDPROXY_CLIENTINFO' in os.environ:
        ClientInfo = bool(os.environ['FDPROXY_CLIENTINFO'])
    if 'FDPROXY_LISTENPORT' in os.environ:
        ListenPort = os.environ['FDPROXY_LISTENPORT']
        
    
    CONNTRACK = {}

    for port in range(DestportStart,DestPortEnd+1,1):
        CONNTRACK[port] = False
    
    #If we are listening IPv6 and Master is an IPv4 IPv4Address
    #IPv6ify the address. 
    if ListenIP == '::' and IsIPv4Address(Master):
        Master = '::ffff:' + Master

    reactor.listenUDP(ListenPort,Proxy(Master,ListenPort,CONNTRACK,BlackList,Timeout,Debug,ClientInfo,DestportStart,DestPortEnd),interface=ListenIP)

    def loopingErrHandle(failure):
        logger.info('(GLOBAL) STOPPING REACTOR TO AVOID MEMORY LEAK: Unhandled error innowtimed loop.\n {}'.format(failure))
        reactor.stop()
        
    def stats():        
        count = 0
        nowtime = time()
        for port in CONNTRACK:
            if CONNTRACK[port]:
                count = count+1
                
        totalPorts = DestPortEnd - DestportStart
        freePorts = totalPorts - count
        
        logger.info("{} ports out of {} in use ({} free)".format(count,totalPorts,freePorts))


        
    if Stats == True:
        stats_task = task.LoopingCall(stats)
        statsa = stats_task.start(30)
        statsa.addErrback(loopingErrHandle)
    

# Used to track if we have downloaded user custon rules
user_rules = {}

# Dictionary for dynamically mapping unit (subscriber) to a system.
# This is for pruning unit-to-uint calls to not broadcast once the
# target system for a unit is identified
# format 'unit_id': ('SYSTEM', time)
UNIT_MAP = {} 
BRIDGES = {}

# Timed loop used for reporting HBP status
#
# REPORT BASED ON THE TYPE SELECTED IN THE MAIN CONFIG FILE
def config_reports(_config, _factory):
    if True: #_config['REPORTS']['REPORT']:
        def reporting_loop(logger, _server):
            logger.debug('(REPORT) Periodic reporting loop started')
            _server.send_config()
            _server.send_bridge()

        logger.info('(REPORT) HBlink TCP reporting server configured')

        report_server = _factory(_config)
        report_server.clients = []
        reactor.listenTCP(_config['REPORTS']['REPORT_PORT'], report_server)

        reporting = task.LoopingCall(reporting_loop, logger, report_server)
        reporting.start(_config['REPORTS']['REPORT_INTERVAL'])

    return report_server
# Send peer data that needs to be sent to APRS
def svrd_send_aprs_peer(_svrd_data):
    _svrd_packet = SVRD
    for system in CONFIG['SYSTEMS']:
        if CONFIG['SYSTEMS'][system]['ENABLED']:
                if CONFIG['SYSTEMS'][system]['MODE'] == 'OPENBRIDGE':
                    if 'PEER_APRS' in CONFIG['SYSTEMS'][system]['OTHER_OPTIONS']:
                        systems[system].send_system(SVRD + b'APRS' + str.encode(str(_svrd_data)))

# Send data to all OBP connections that have an encryption key. Data such as subscribers are sent to other HBNet servers.
def svrd_send_all(_svrd_data):
    _svrd_packet = SVRD
    for system in CONFIG['SYSTEMS']:
        if CONFIG['SYSTEMS'][system]['ENABLED']:
                if CONFIG['SYSTEMS'][system]['MODE'] == 'OPENBRIDGE':
                    if CONFIG['SYSTEMS'][system]['ENCRYPTION_KEY'] != b'':
                        systems[system].send_system(_svrd_packet + _svrd_data)
                        
# Send any data packets to connections with ALL_DATA specified in other options
def mirror_traffic(_data):
    for system in CONFIG['SYSTEMS']:
        if CONFIG['SYSTEMS'][system]['ENABLED']:
                if CONFIG['SYSTEMS'][system]['MODE'] == 'OPENBRIDGE':
##                    print(CONFIG['SYSTEMS'][system]['OTHER_OPTIONS'])
                    if 'MIRROR_DATA' in CONFIG['SYSTEMS'][system]['OTHER_OPTIONS']:
                        systems[system].send_system(SVRD + b'MDAT' + _data)

# def all_unit_mmdvm_peer(_data):
#     for system in CONFIG['SYSTEMS']:
#         if CONFIG['SYSTEMS'][system]['ENABLED']:
#                 if CONFIG['SYSTEMS'][system]['MODE'] == 'PEER':
#                     if b'ALL_MMDVM_UNIT' in CONFIG['SYSTEMS'][system]['OPTIONS']:
#                         systems[system].send_system(_data)

def expose_all(_data):
    for system in CONFIG['SYSTEMS']:
        if CONFIG['SYSTEMS'][system]['ENABLED']:
                if CONFIG['SYSTEMS'][system]['MODE'] == 'PEER':
                    if 'EXPOSE_ALL' in CONFIG['SYSTEMS'][system]['OTHER_OPTIONS']:
                        systems[system].send_system(_data)
                if CONFIG['SYSTEMS'][system]['MODE'] == 'OPENBRIDGE':
##                    print(CONFIG['SYSTEMS'][system]['OTHER_OPTIONS'])
                    if 'EXPOSE_ALL' in CONFIG['SYSTEMS'][system]['OTHER_OPTIONS']:
                        systems[system].send_system(SVRD + b'MDAT' + _data)

                    


# Add PROXY instances to UNIT
def gen_proxy_unit(UNIT):
    NEW_UNIT = copy.deepcopy(UNIT)
    for u in UNIT:
        if LOCAL_CONFIG['SYSTEMS'][u]['MODE'] == 'PROXY':
            _prox_n = LOCAL_CONFIG['SYSTEMS'][u]['INTERNAL_PORT_STOP'] - LOCAL_CONFIG['SYSTEMS'][u]['INTERNAL_PORT_START']
            _count_n = 0
            while _count_n < _prox_n:
                if _count_n == 0:
                    NEW_UNIT.append(u + '-0')

                else:
                    NEW_UNIT.append(u + '-' + str(_count_n))
                _count_n = _count_n + 1
            NEW_UNIT.remove(u)
##    print(NEW_UNIT)
    return NEW_UNIT

# Import Bridging rules
# Note: A stanza *must* exist for any MASTER or CLIENT configured in the main
# configuration file and listed as "active". It can be empty,
# but it has to exist.
def make_bridges(_rules, _web_serv_status):
    _new_rules = copy.deepcopy(_rules)
##    print(LOCAL_CONFIG)
    if LOCAL_CONFIG['WEB_SERVICE']['REMOTE_CONFIG_ENABLED'] == False or _web_serv_status == False:
        for _bridge in _rules:
            for _system in _rules[_bridge]:
                if LOCAL_CONFIG['SYSTEMS'][_system['SYSTEM']]['MODE'] == 'PROXY': 
                    for _sys in CONFIG['SYSTEMS']:

                        if re.sub('-.*','', _sys) == _system['SYSTEM']:
                            for prx in _rules[_bridge]:
                                if prx['SYSTEM'] == _system['SYSTEM']:
                                    _new_rules[_bridge].append({'SYSTEM':_sys, 'TS': prx['TS'], 'TGID': prx['TGID'], 'ACTIVE': prx['ACTIVE'], 'TIMEOUT': prx['TIMEOUT'], 'TO_TYPE': prx['TO_TYPE'], 'ON': prx['ON'], 'OFF': prx['OFF'], 'RESET': prx['RESET']})
            for _orig in _new_rules[_bridge]:
                if _orig['SYSTEM'] in LOCAL_CONFIG['SYSTEMS'] and LOCAL_CONFIG['SYSTEMS'][_orig['SYSTEM']]['MODE'] == 'PROXY':
                    _new_rules[_bridge].remove(_orig)
                                     
    # Convert integer GROUP ID numbers from the config into hex strings
    # we need to send in the actual data packets.
    for _bridge in _new_rules:
        for _system in _new_rules[_bridge]:
            if _system['SYSTEM'] not in CONFIG['SYSTEMS']:
                sys.exit('ERROR: Conference bridge "{}" references a system named "{}" that is not enabled in the main configuration'.format(_bridge, _system['SYSTEM']))

            _system['TGID']       = bytes_3(_system['TGID'])
            for i, e in enumerate(_system['ON']):
                if type(_system['ON'][i]) == bytes:
                    pass
                else:
                    _system['ON'][i]  = bytes_3(_system['ON'][i])
            for i, e in enumerate(_system['OFF']):
                if type(_system['OFF'][i]) == bytes:
                    pass
                else:
                    _system['OFF'][i] = bytes_3(_system['OFF'][i])
            _system['TIMEOUT']    = _system['TIMEOUT']*60
            if _system['ACTIVE'] == True:
                _system['TIMER']  = time() + _system['TIMEOUT']
            else:
                _system['TIMER']  = time()
    return _new_rules

def ten_loop_func():
    logger.info('10 minute function loop')
    # Download burn list
    if LOCAL_CONFIG['WEB_SERVICE']['REMOTE_CONFIG_ENABLED']:
        with open(CONFIG['WEB_SERVICE']['BURN_FILE'], 'w') as f:
            f.write(str(download_burnlist(CONFIG)))

def user_systems():
    if Path('/tmp/' + (CONFIG['LOGGER']['LOG_NAME'] + '_PEERS/')).exists():
        pass
    else:
        Path('/tmp/' + (CONFIG['LOGGER']['LOG_NAME'] + '_PEERS/')).mkdir()
    peer_files = os.listdir('/tmp/' + CONFIG['LOGGER']['LOG_NAME'] + '_PEERS/')
    whos_where = {}
    for i in peer_files:
        if '.' not in i:
            # print(i)
            data = ast.literal_eval(os.popen('cat /tmp/' + (CONFIG['LOGGER']['LOG_NAME'] + '_PEERS/' + i)).read())
##            where_list = {}
            whos_where[i] = []
            for d in data.items():
                # print(d[1]['call'])
                whos_where[i].append(d[1]['call'])
##                whos_where.append({i:d[1]['call']})
##    print(whos_where)
    return whos_where
##    ast.literal_eval(os.popen('cat /tmp/' + (CONFIG['LOGGER']['LOG_NAME'] + '_PEERS/' + system)).read())

                
# Run this every minute for rule timer updates
def rule_timer_loop(unit_flood_time):
    global UNIT_MAP
##    print(HBSYSTEM('HOTSPOT', CONFIG, '')._peers)
    logger.debug('(ROUTER) routerHBP Rule timer loop started')
    _now = time()
    #This is a good place to get and modify rules for users
##    print(BRIDGES)
    for _bridge in BRIDGES:
        for _system in BRIDGES[_bridge]:
            if _system['TO_TYPE'] == 'ON':
                if _system['ACTIVE'] == True:
                    if _system['TIMER'] < _now:
                        _system['ACTIVE'] = False
                        logger.info('(ROUTER) Conference Bridge TIMEOUT: DEACTIVATE System: %s, Bridge: %s, TS: %s, TGID: %s', _system['SYSTEM'], _bridge, _system['TS'], int_id(_system['TGID']))
                        # Send not active POST
                        #update_tg(CONFIG, 'off', 0, [{'SYSTEM':_system['SYSTEM']}, {'ts':_system['TS']}, {'tg': int_id(_system['TGID'])}])

##                        print(_system)
                    else:
                        timeout_in = _system['TIMER'] - _now
                        logger.info('(ROUTER) Conference Bridge ACTIVE (ON timer running): System: %s Bridge: %s, TS: %s, TGID: %s, Timeout in: %.2fs,', _system['SYSTEM'], _bridge, _system['TS'], int_id(_system['TGID']),  timeout_in)
                elif _system['ACTIVE'] == False:
                    logger.debug('(ROUTER) Conference Bridge INACTIVE (no change): System: %s Bridge: %s, TS: %s, TGID: %s', _system['SYSTEM'], _bridge, _system['TS'], int_id(_system['TGID']))
            elif _system['TO_TYPE'] == 'OFF':
                if _system['ACTIVE'] == False:
                    if _system['TIMER'] < _now:
                        _system['ACTIVE'] = True
                        logger.info('(ROUTER) Conference Bridge TIMEOUT: ACTIVATE System: %s, Bridge: %s, TS: %s, TGID: %s', _system['SYSTEM'], _bridge, _system['TS'], int_id(_system['TGID']))
                        # POST ON
##                        update_tg(CONFIG, 'on', 0, [{'SYSTEM':_system['SYSTEM']}, {'ts':_system['TS']}, {'tg': int_id(_system['TGID'])}])
                    else:
                        timeout_in = _system['TIMER'] - _now
                        logger.info('(ROUTER) Conference Bridge INACTIVE (OFF timer running): System: %s Bridge: %s, TS: %s, TGID: %s, Timeout in: %.2fs,', _system['SYSTEM'], _bridge, _system['TS'], int_id(_system['TGID']),  timeout_in)
                elif _system['ACTIVE'] == True:
                    logger.debug('(ROUTER) Conference Bridge ACTIVE (no change): System: %s Bridge: %s, TS: %s, TGID: %s', _system['SYSTEM'], _bridge, _system['TS'], int_id(_system['TGID']))
                    # POST on
##                    print(_system)
##                    update_tg(CONFIG, 'on', 0, [{'SYSTEM':_system['SYSTEM']}, {'ts':_system['TS']}, {'tg': int_id(_system['TGID'])}])
            else:
                logger.debug('(ROUTER) Conference Bridge NO ACTION: System: %s, Bridge: %s, TS: %s, TGID: %s', _system['SYSTEM'], _bridge, _system['TS'], int_id(_system['TGID']))

##    for unit in UNIT_MAP:
##        svrd_send_all(b'UNIT' + unit)
    _then = _now - unit_flood_time
    remove_list = []
    for unit in UNIT_MAP:
        if UNIT_MAP[unit][1] < (_then):
            remove_list.append(unit)

    for unit in remove_list:
        del UNIT_MAP[unit]
    send_unit_table(CONFIG, UNIT_MAP)

    logger.debug('Removed unit(s) %s from UNIT_MAP', remove_list)


    if CONFIG['REPORTS']['REPORT']:
        report_server.send_clients(b'bridge updated')

    # Send PEER info to data gateway for APRS packet generation
    try:    
        for system in CONFIG['SYSTEMS']:
            if CONFIG['SYSTEMS'][system]['ENABLED']:
                    if CONFIG['SYSTEMS'][system]['MODE'] == 'MASTER' or CONFIG['SYSTEMS'][system]['MODE'] == 'PROXY':
                        if CONFIG['SYSTEMS'][system]['STATIC_APRS_POSITION_ENABLED'] == True:
                            dict_data = ast.literal_eval(os.popen('cat /tmp/' + (CONFIG['LOGGER']['LOG_NAME'] + '_PEERS/' + system)).read())
                            svrd_send_aprs_peer(dict_data)
    except Exception as e:
        logger.error(e)


# run this every 10 seconds to trim orphaned stream ids
def stream_trimmer_loop():
    ping(CONFIG, BRIDGES)
    logger.debug('(ROUTER) Trimming inactive stream IDs from system lists')
    _now = time()

    for system in systems:
        # HBP systems, master and peer
        if CONFIG['SYSTEMS'][system]['MODE'] != 'OPENBRIDGE':
            for slot in range(1,3):
                _slot  = systems[system].STATUS[slot]

                # RX slot check
                if _slot['RX_TYPE'] != HBPF_SLT_VTERM and _slot['RX_TIME'] <  _now - 5:
                    _slot['RX_TYPE'] = HBPF_SLT_VTERM
                    logger.info('(%s) *TIME OUT*  RX STREAM ID: %s SUB: %s TGID %s, TS %s, Duration: %.2f', \
                        system, int_id(_slot['RX_STREAM_ID']), int_id(_slot['RX_RFS']), int_id(_slot['RX_TGID']), slot, _slot['RX_TIME'] - _slot['RX_START'])
                    if CONFIG['REPORTS']['REPORT']:
                        systems[system]._report.send_bridgeEvent('GROUP VOICE,END,RX,{},{},{},{},{},{},{:.2f}'.format(system, int_id(_slot['RX_STREAM_ID']), int_id(_slot['RX_PEER']), int_id(_slot['RX_RFS']), slot, int_id(_slot['RX_TGID']), _slot['RX_TIME'] - _slot['RX_START']).encode(encoding='utf-8', errors='ignore'))

                # TX slot check
                if _slot['TX_TYPE'] != HBPF_SLT_VTERM and _slot['TX_TIME'] <  _now - 5:
                    _slot['TX_TYPE'] = HBPF_SLT_VTERM
                    logger.info('(%s) *TIME OUT*  TX STREAM ID: %s SUB: %s TGID %s, TS %s, Duration: %.2f', \
                        system, int_id(_slot['TX_STREAM_ID']), int_id(_slot['TX_RFS']), int_id(_slot['TX_TGID']), slot, _slot['TX_TIME'] - _slot['TX_START'])
                    if CONFIG['REPORTS']['REPORT']:
                        systems[system]._report.send_bridgeEvent('GROUP VOICE,END,TX,{},{},{},{},{},{},{:.2f}'.format(system, int_id(_slot['TX_STREAM_ID']), int_id(_slot['TX_PEER']), int_id(_slot['TX_RFS']), slot, int_id(_slot['TX_TGID']), _slot['TX_TIME'] - _slot['TX_START']).encode(encoding='utf-8', errors='ignore'))

        # OBP systems
        # We can't delete items from a dicationry that's being iterated, so we have to make a temporarly list of entrys to remove later
        if CONFIG['SYSTEMS'][system]['MODE'] == 'OPENBRIDGE':
            remove_list = []
            for stream_id in systems[system].STATUS:
                if systems[system].STATUS[stream_id]['LAST'] < _now - 5:
                    remove_list.append(stream_id)
            for stream_id in remove_list:
                if stream_id in systems[system].STATUS:
                    _stream = systems[system].STATUS[stream_id]
                    _sysconfig = CONFIG['SYSTEMS'][system]
                    if systems[system].STATUS[stream_id]['ACTIVE']:
                        logger.info('(%s) *TIME OUT*   STREAM ID: %s SUB: %s PEER: %s TYPE: %s DST ID: %s TS 1 Duration: %.2f', \
                        system, int_id(stream_id), get_alias(int_id(_stream['RFS']), subscriber_ids), get_alias(int_id(_sysconfig['NETWORK_ID']), peer_ids), _stream['TYPE'], get_alias(int_id(_stream['DST']), talkgroup_ids), _stream['LAST'] - _stream['START'])
                    if CONFIG['REPORTS']['REPORT']:
                            if _stream['TYPE'] == 'GROUP':
                                systems[system]._report.send_bridgeEvent('GROUP VOICE,END,RX,{},{},{},{},{},{},{:.2f}'.format(system, int_id(stream_id), int_id(_sysconfig['NETWORK_ID']), int_id(_stream['RFS']), 1, int_id(_stream['DST']), _stream['LAST'] - _stream['START']).encode(encoding='utf-8', errors='ignore'))
                            elif _stream['TYPE'] == 'UNIT':
                                systems[system]._report.send_bridgeEvent('UNIT VOICE,END,RX,{},{},{},{},{},{},{:.2f}'.format(system, int_id(stream_id), int_id(_sysconfig['NETWORK_ID']), int_id(_stream['RFS']), 1, int_id(_stream['DST']), _stream['LAST'] - _stream['START']).encode(encoding='utf-8', errors='ignore'))
                    removed = systems[system].STATUS.pop(stream_id)
                else:
                    logger.error('(%s) Attemped to remove OpenBridge Stream ID %s not in the Stream ID list: %s', system, int_id(stream_id), [id for id in systems[system].STATUS])

class routerOBP(OPENBRIDGE):

    def __init__(self, _name, _config, _report):
        OPENBRIDGE.__init__(self, _name, _config, _report)
        self.name = _name
        self.STATUS = {}
        
        # list of self._targets for unit (subscriber, private) calls
        self._targets = []

    def svrd_received(self, _mode, _data):
##        print(UNIT_MAP)
        logger.info('SVRD Received. Mode: ' + str(_mode) + ' Data: ' + str(_data))
        if _mode == b'UNIT':
            UNIT_MAP[_data] = (self._system, time())

    def group_received(self, _peer_id, _rf_src, _dst_id, _seq, _slot, _frame_type, _dtype_vseq, _stream_id, _data):
        pkt_time = time()
        dmrpkt = _data[20:53]
        _bits = _data[15]
        
        # Is this a new call stream?
        if (_stream_id not in self.STATUS):
            # This is a new call stream
            self.STATUS[_stream_id] = {
                'START':     pkt_time,
                'CONTENTION':False,
                'RFS':       _rf_src,
                'TYPE':      'GROUP',
                'DST':       _dst_id,
                'ACTIVE':    True
            }

            # If we can, use the LC from the voice header as to keep all options intact
            if _frame_type == HBPF_DATA_SYNC and _dtype_vseq == HBPF_SLT_VHEAD:
                decoded = decode.voice_head_term(dmrpkt)
                self.STATUS[_stream_id]['LC'] = decoded['LC']

            # If we don't have a voice header then don't wait to decode the Embedded LC
            # just make a new one from the HBP header. This is good enough, and it saves lots of time
            else:
                self.STATUS[_stream_id]['LC'] = LC_OPT + _dst_id + _rf_src


            logger.info('(%s) *GROUP CALL START* OBP STREAM ID: %s SUB: %s (%s) PEER: %s (%s) TGID %s (%s), TS %s', \
                    self._system, int_id(_stream_id), get_alias(_rf_src, subscriber_ids), int_id(_rf_src), get_alias(_peer_id, peer_ids), int_id(_peer_id), get_alias(_dst_id, talkgroup_ids), int_id(_dst_id), _slot)
            if CONFIG['REPORTS']['REPORT']:
                self._report.send_bridgeEvent('GROUP VOICE,START,RX,{},{},{},{},{},{}'.format(self._system, int_id(_stream_id), int_id(_peer_id), int_id(_rf_src), _slot, int_id(_dst_id)).encode(encoding='utf-8', errors='ignore'))

        self.STATUS[_stream_id]['LAST'] = pkt_time


        for _bridge in BRIDGES:
            for _system in BRIDGES[_bridge]:

                if (_system['SYSTEM'] == self._system and _system['TGID'] == _dst_id and _system['TS'] == _slot and _system['ACTIVE'] == True):

                    for _target in BRIDGES[_bridge]:
                        if (_target['SYSTEM'] != self._system) and (_target['ACTIVE']):
                            _target_status = systems[_target['SYSTEM']].STATUS
                            _target_system = self._CONFIG['SYSTEMS'][_target['SYSTEM']]
                            if _target_system['MODE'] == 'OPENBRIDGE':
                                # Is this a new call stream on the target?
                                if (_stream_id not in _target_status):
                                    # This is a new call stream on the target
                                    _target_status[_stream_id] = {
                                        'START':     pkt_time,
                                        'CONTENTION':False,
                                        'RFS':       _rf_src,
                                        'TYPE':      'GROUP',
                                        'DST':       _dst_id,
                                        'ACTIVE':    True
                                    }
                                    # Generate LCs (full and EMB) for the TX stream
                                    dst_lc = b''.join([self.STATUS[_stream_id]['LC'][0:3], _target['TGID'], _rf_src])
                                    _target_status[_stream_id]['H_LC'] = bptc.encode_header_lc(dst_lc)
                                    _target_status[_stream_id]['T_LC'] = bptc.encode_terminator_lc(dst_lc)
                                    _target_status[_stream_id]['EMB_LC'] = bptc.encode_emblc(dst_lc)

                                    logger.info('(%s) Conference Bridge: %s, Call Bridged to OBP System: %s TS: %s, TGID: %s', self._system, _bridge, _target['SYSTEM'], _target['TS'], int_id(_target['TGID']))
                                    if CONFIG['REPORTS']['REPORT']:
                                        systems[_target['SYSTEM']]._report.send_bridgeEvent('GROUP VOICE,START,TX,{},{},{},{},{},{}'.format(_target['SYSTEM'], int_id(_stream_id), int_id(_peer_id), int_id(_rf_src), _target['TS'], int_id(_target['TGID'])).encode(encoding='utf-8', errors='ignore'))

                                # Record the time of this packet so we can later identify a stale stream
                                _target_status[_stream_id]['LAST'] = pkt_time
                                # Clear the TS bit -- all OpenBridge streams are effectively on TS1
                                _tmp_bits = _bits & ~(1 << 7)

                                # Assemble transmit HBP packet header
                                _tmp_data = b''.join([_data[:8], _target['TGID'], _data[11:15], _tmp_bits.to_bytes(1, 'big'), _data[16:20]])

                                # MUST TEST FOR NEW STREAM AND IF SO, RE-WRITE THE LC FOR THE TARGET
                                # MUST RE-WRITE DESTINATION TGID IF DIFFERENT
                                # if _dst_id != rule['DST_GROUP']:
                                dmrbits = bitarray(endian='big')
                                dmrbits.frombytes(dmrpkt)
                                # Create a voice header packet (FULL LC)
                                if _frame_type == HBPF_DATA_SYNC and _dtype_vseq == HBPF_SLT_VHEAD:
                                    dmrbits = _target_status[_stream_id]['H_LC'][0:98] + dmrbits[98:166] + _target_status[_stream_id]['H_LC'][98:197]
                                # Create a voice terminator packet (FULL LC)
                                elif _frame_type == HBPF_DATA_SYNC and _dtype_vseq == HBPF_SLT_VTERM:
                                    dmrbits = _target_status[_stream_id]['T_LC'][0:98] + dmrbits[98:166] + _target_status[_stream_id]['T_LC'][98:197]
                                    if CONFIG['REPORTS']['REPORT']:
                                        call_duration = pkt_time - _target_status[_stream_id]['START']
                                        _target_status[_stream_id]['ACTIVE'] = False
                                        systems[_target['SYSTEM']]._report.send_bridgeEvent('GROUP VOICE,END,TX,{},{},{},{},{},{},{:.2f}'.format(_target['SYSTEM'], int_id(_stream_id), int_id(_peer_id), int_id(_rf_src), _target['TS'], int_id(_target['TGID']), call_duration).encode(encoding='utf-8', errors='ignore'))              
                                # Create a Burst B-E packet (Embedded LC)
                                elif _dtype_vseq in [1,2,3,4]:
                                    dmrbits = dmrbits[0:116] + _target_status[_stream_id]['EMB_LC'][_dtype_vseq] + dmrbits[148:264]
                                dmrpkt = dmrbits.tobytes()
                                _tmp_data = b''.join([_tmp_data, dmrpkt])

                            else:
                                # BEGIN CONTENTION HANDLING
                                #
                                # The rules for each of the 4 "ifs" below are listed here for readability. The Frame To Send is:
                                #   From a different group than last RX from this HBSystem, but it has been less than Group Hangtime
                                #   From a different group than last TX to this HBSystem, but it has been less than Group Hangtime
                                #   From the same group as the last RX from this HBSystem, but from a different subscriber, and it has been less than stream timeout
                                #   From the same group as the last TX to this HBSystem, but from a different subscriber, and it has been less than stream timeout
                                # The "continue" at the end of each means the next iteration of the for loop that tests for matching rules
                                #
                                if ((_target['TGID'] != _target_status[_target['TS']]['RX_TGID']) and ((pkt_time - _target_status[_target['TS']]['RX_TIME']) < _target_system['GROUP_HANGTIME'])):
                                    if self.STATUS[_stream_id]['CONTENTION'] == False:
                                        self.STATUS[_stream_id]['CONTENTION'] = True
                                        logger.info('(%s) Call not routed to TGID %s, target active or in group hangtime: HBSystem: %s, TS: %s, TGID: %s', self._system, int_id(_target['TGID']), _target['SYSTEM'], _target['TS'], int_id(_target_status[_target['TS']]['RX_TGID']))
                                    continue
                                if ((_target['TGID'] != _target_status[_target['TS']]['TX_TGID']) and ((pkt_time - _target_status[_target['TS']]['TX_TIME']) < _target_system['GROUP_HANGTIME'])):
                                    if self.STATUS[_stream_id]['CONTENTION'] == False:
                                        self.STATUS[_stream_id]['CONTENTION'] = True
                                        logger.info('(%s) Call not routed to TGID%s, target in group hangtime: HBSystem: %s, TS: %s, TGID: %s', self._system, int_id(_target['TGID']), _target['SYSTEM'], _target['TS'], int_id(_target_status[_target['TS']]['TX_TGID']))
                                    continue
                                if (_target['TGID'] == _target_status[_target['TS']]['RX_TGID']) and ((pkt_time - _target_status[_target['TS']]['RX_TIME']) < STREAM_TO):
                                    if self.STATUS[_stream_id]['CONTENTION'] == False:
                                        self.STATUS[_stream_id]['CONTENTION'] = True
                                        logger.info('(%s) Call not routed to TGID%s, matching call already active on target: HBSystem: %s, TS: %s, TGID: %s', self._system, int_id(_target['TGID']), _target['SYSTEM'], _target['TS'], int_id(_target_status[_target['TS']]['RX_TGID']))
                                    continue
                                if (_target['TGID'] == _target_status[_target['TS']]['TX_TGID']) and (_rf_src != _target_status[_target['TS']]['TX_RFS']) and ((pkt_time - _target_status[_target['TS']]['TX_TIME']) < STREAM_TO):
                                    if self.STATUS[_stream_id]['CONTENTION'] == False:
                                        self.STATUS[_stream_id]['CONTENTION'] = True
                                        logger.info('(%s) Call not routed for subscriber %s, call route in progress on target: HBSystem: %s, TS: %s, TGID: %s, SUB: %s', self._system, int_id(_rf_src), _target['SYSTEM'], _target['TS'], int_id(_target_status[_target['TS']]['TX_TGID']), int_id(_target_status[_target['TS']]['TX_RFS']))
                                    continue

                                # Is this a new call stream?
                                if (_target_status[_target['TS']]['TX_STREAM_ID'] != _stream_id):
                                    # Record the DST TGID and Stream ID
                                    _target_status[_target['TS']]['TX_START'] = pkt_time
                                    _target_status[_target['TS']]['TX_TGID'] = _target['TGID']
                                    _target_status[_target['TS']]['TX_STREAM_ID'] = _stream_id
                                    _target_status[_target['TS']]['TX_RFS'] = _rf_src
                                    _target_status[_target['TS']]['TX_PEER'] = _peer_id
                                    # Generate LCs (full and EMB) for the TX stream
                                    dst_lc = b''.join([self.STATUS[_stream_id]['LC'][0:3], _target['TGID'], _rf_src])
                                    _target_status[_target['TS']]['TX_H_LC'] = bptc.encode_header_lc(dst_lc)
                                    _target_status[_target['TS']]['TX_T_LC'] = bptc.encode_terminator_lc(dst_lc)
                                    _target_status[_target['TS']]['TX_EMB_LC'] = bptc.encode_emblc(dst_lc)
                                    logger.debug('(%s) Generating TX FULL and EMB LCs for HomeBrew destination: System: %s, TS: %s, TGID: %s', self._system, _target['SYSTEM'], _target['TS'], int_id(_target['TGID']))
                                    logger.info('(%s) Conference Bridge: %s, Call Bridged to HBP System: %s TS: %s, TGID: %s', self._system, _bridge, _target['SYSTEM'], _target['TS'], int_id(_target['TGID']))
                                    if CONFIG['REPORTS']['REPORT']:
                                       systems[_target['SYSTEM']]._report.send_bridgeEvent('GROUP VOICE,START,TX,{},{},{},{},{},{}'.format(_target['SYSTEM'], int_id(_stream_id), int_id(_peer_id), int_id(_rf_src), _target['TS'], int_id(_target['TGID'])).encode(encoding='utf-8', errors='ignore'))

                                # Set other values for the contention handler to test next time there is a frame to forward
                                _target_status[_target['TS']]['TX_TIME'] = pkt_time
                                _target_status[_target['TS']]['TX_TYPE'] = _dtype_vseq

                                # Handle any necessary re-writes for the destination
                                if _system['TS'] != _target['TS']:
                                    _tmp_bits = _bits ^ 1 << 7
                                else:
                                    _tmp_bits = _bits

                                # Assemble transmit HBP packet header
                                _tmp_data = b''.join([_data[:8], _target['TGID'], _data[11:15], _tmp_bits.to_bytes(1, 'big'), _data[16:20]])

                                # MUST TEST FOR NEW STREAM AND IF SO, RE-WRITE THE LC FOR THE TARGET
                                # MUST RE-WRITE DESTINATION TGID IF DIFFERENT
                                # if _dst_id != rule['DST_GROUP']:
                                dmrbits = bitarray(endian='big')
                                dmrbits.frombytes(dmrpkt)
                                # Create a voice header packet (FULL LC)
                                if _frame_type == HBPF_DATA_SYNC and _dtype_vseq == HBPF_SLT_VHEAD:
                                    dmrbits = _target_status[_target['TS']]['TX_H_LC'][0:98] + dmrbits[98:166] + _target_status[_target['TS']]['TX_H_LC'][98:197]
                                # Create a voice terminator packet (FULL LC)
                                elif _frame_type == HBPF_DATA_SYNC and _dtype_vseq == HBPF_SLT_VTERM:
                                    dmrbits = _target_status[_target['TS']]['TX_T_LC'][0:98] + dmrbits[98:166] + _target_status[_target['TS']]['TX_T_LC'][98:197]
                                    if CONFIG['REPORTS']['REPORT']:
                                        call_duration = pkt_time - _target_status[_target['TS']]['TX_START']
                                        systems[_target['SYSTEM']]._report.send_bridgeEvent('GROUP VOICE,END,TX,{},{},{},{},{},{},{:.2f}'.format(_target['SYSTEM'], int_id(_stream_id), int_id(_peer_id), int_id(_rf_src), _target['TS'], int_id(_target['TGID']), call_duration).encode(encoding='utf-8', errors='ignore'))
                                # Create a Burst B-E packet (Embedded LC)
                                elif _dtype_vseq in [1,2,3,4]:
                                    dmrbits = dmrbits[0:116] + _target_status[_target['TS']]['TX_EMB_LC'][_dtype_vseq] + dmrbits[148:264]
                                dmrpkt = dmrbits.tobytes()
                                _tmp_data = b''.join([_tmp_data, dmrpkt, b'\x00\x00']) # Add two bytes of nothing since OBP doesn't include BER & RSSI bytes #_data[53:55]

                            # Transmit the packet to the destination system
                            systems[_target['SYSTEM']].send_system(_tmp_data)
                            #logger.debug('(%s) Packet routed by bridge: %s to system: %s TS: %s, TGID: %s', self._system, _bridge, _target['SYSTEM'], _target['TS'], int_id(_target['TGID']))


        # Final actions - Is this a voice terminator?
        if (_frame_type == HBPF_DATA_SYNC) and (_dtype_vseq == HBPF_SLT_VTERM):
            call_duration = pkt_time - self.STATUS[_stream_id]['START']
            logger.info('(%s) *GROUP CALL END*   STREAM ID: %s SUB: %s (%s) PEER: %s (%s) TGID %s (%s), TS %s, Duration: %.2f', \
                    self._system, int_id(_stream_id), get_alias(_rf_src, subscriber_ids), int_id(_rf_src), get_alias(_peer_id, peer_ids), int_id(_peer_id), get_alias(_dst_id, talkgroup_ids), int_id(_dst_id), _slot, call_duration)
            if CONFIG['REPORTS']['REPORT']:
               self._report.send_bridgeEvent('GROUP VOICE,END,RX,{},{},{},{},{},{},{:.2f}'.format(self._system, int_id(_stream_id), int_id(_peer_id), int_id(_rf_src), _slot, int_id(_dst_id), call_duration).encode(encoding='utf-8', errors='ignore'))
            self.STATUS[_stream_id]['ACTIVE'] = False
            logger.debug('(%s) OpenBridge sourced call stream end, remove terminated Stream ID: %s', self._system, int_id(_stream_id))


    def unit_received(self, _peer_id, _rf_src, _dst_id, _seq, _slot, _frame_type, _dtype_vseq, _stream_id, _data):
        global UNIT_MAP
        pkt_time = time()
        dmrpkt = _data[20:53]
        _bits = _data[15]

        logger.debug('Src: ' + str(int_id(_rf_src)))
        logger.debug('Dst: ' + str(int_id(_dst_id)))
 
        # Make/update this unit in the UNIT_MAP cache
        UNIT_MAP[_rf_src] = (self.name, pkt_time)

        # Send update to all OpenBridge connections
##        svrd_send_all(b'UNIT' + _rf_src) # + b'TIME' + pkt_time)
        
        
        # Is this a new call stream?
        if (_stream_id not in self.STATUS):
            # This is a new call stream
            self.STATUS[_stream_id] = {
                'START':     pkt_time,
                'CONTENTION':False,
                'RFS':       _rf_src,
                'TYPE':      'UNIT',
                'DST':       _dst_id,
                'ACTIVE':    True
            }
                
            # Create a destination list for the call:                
            if _dst_id in UNIT_MAP:
                if UNIT_MAP[_dst_id][0] != self._system:
                    self._targets = [UNIT_MAP[_dst_id][0]]
                else:
                    self._targets = []
                    logger.error('UNIT call to a subscriber on the same system, send nothing')
            else:
                self._targets = list(UNIT)
                self._targets.remove(self._system)
            
            
            # This is a new call stream, so log & report
            logger.info('(%s) *UNIT CALL START* STREAM ID: %s SUB: %s (%s) PEER: %s (%s) UNIT: %s (%s), TS: %s, FORWARD: %s', \
                    self._system, int_id(_stream_id), get_alias(_rf_src, subscriber_ids), int_id(_rf_src), get_alias(_peer_id, peer_ids), int_id(_peer_id), get_alias(_dst_id, talkgroup_ids), int_id(_dst_id), _slot, self._targets)
            if CONFIG['REPORTS']['REPORT']:
                self._report.send_bridgeEvent('UNIT VOICE,START,RX,{},{},{},{},{},{},{}'.format(self._system, int_id(_stream_id), int_id(_peer_id), int_id(_rf_src), _slot, int_id(_dst_id), self._targets).encode(encoding='utf-8', errors='ignore'))

        # Record the time of this packet so we can later identify a stale stream
        self.STATUS[_stream_id]['LAST'] = pkt_time

        for _target in self._targets:
            _target_status = systems[_target].STATUS
            _target_system = self._CONFIG['SYSTEMS'][_target]
            
            if self._CONFIG['SYSTEMS'][_target]['MODE'] == 'OPENBRIDGE':
                if (_stream_id not in _target_status):
                    # This is a new call stream on the target
                    _target_status[_stream_id] = {
                        'START':     pkt_time,
                        'CONTENTION':False,
                        'RFS':       _rf_src,
                        'TYPE':      'UNIT',
                        'DST':      _dst_id,
                        'ACTIVE':   True
                    }

                    logger.info('(%s) Unit call bridged to OBP System: %s TS: %s, TGID: %s', self._system, _target, _slot if _target_system['BOTH_SLOTS'] else 1, int_id(_dst_id))
                    if CONFIG['REPORTS']['REPORT']:
                        systems[_target]._report.send_bridgeEvent('UNIT VOICE,START,TX,{},{},{},{},{},{}'.format(_target, int_id(_stream_id), int_id(_peer_id), int_id(_rf_src), _slot, int_id(_dst_id)).encode(encoding='utf-8', errors='ignore'))

                # Record the time of this packet so we can later identify a stale stream
                _target_status[_stream_id]['LAST'] = pkt_time
                # Clear the TS bit and follow propper OBP definition, unless "BOTH_SLOTS" is set. This only works for unit calls.
                if _target_system['BOTH_SLOTS']:
                    _tmp_bits = _bits
                else:
                    _tmp_bits = _bits & ~(1 << 7)

                # Assemble transmit HBP packet
                _tmp_data = b''.join([_data[:15], _tmp_bits.to_bytes(1, 'big'), _data[16:20]])
                _data = b''.join([_tmp_data, dmrpkt])
                
                if (_frame_type == HBPF_DATA_SYNC) and (_dtype_vseq == HBPF_SLT_VTERM):
                    _target_status[_stream_id]['ACTIVE'] = False

            else:
                # BEGIN STANDARD CONTENTION HANDLING
                #
                # The rules for each of the 4 "ifs" below are listed here for readability. The Frame To Send is:
                #   From a different group than last RX from this HBSystem, but it has been less than Group Hangtime
                #   From a different group than last TX to this HBSystem, but it has been less than Group Hangtime
                #   From the same group as the last RX from this HBSystem, but from a different subscriber, and it has been less than stream timeout
                #   From the same group as the last TX to this HBSystem, but from a different subscriber, and it has been less than stream timeout
                # The "continue" at the end of each means the next iteration of the for loop that tests for matching rules
                #
                '''
                if ((_dst_id != _target_status[_slot]['RX_TGID']) and ((pkt_time - _target_status[_slot]['RX_TIME']) < _target_system['GROUP_HANGTIME'])):
                    if self.STATUS[_stream_id]['CONTENTION'] == False:
                        self.STATUS[_stream_id]['CONTENTION'] = True
                        logger.info('(%s) Call not routed to TGID %s, target active or in group hangtime: HBSystem: %s, TS: %s, TGID: %s', self._system, int_id(_dst_id), _target, _slot, int_id(_target_status[_slot]['RX_TGID']))
                    continue
                if ((_dst_id != _target_status[_slot]['TX_TGID']) and ((pkt_time - _target_status[_slot]['TX_TIME']) < _target_system['GROUP_HANGTIME'])):
                    if self.STATUS[_stream_id]['CONTENTION'] == False:
                        self.STATUS[_stream_id]['CONTENTION'] = True
                        logger.info('(%s) Call not routed to TGID%s, target in group hangtime: HBSystem: %s, TS: %s, TGID: %s', self._system, int_id(_dst_id), _target, _slot, int_id(_target_status[_slot]['TX_TGID']))
                    continue
                '''
                if (_dst_id == _target_status[_slot]['RX_TGID']) and ((pkt_time - _target_status[_slot]['RX_TIME']) < STREAM_TO):
                    if self.STATUS[_stream_id]['CONTENTION'] == False:
                        self.STATUS[_stream_id]['CONTENTION'] = True
                        logger.info('(%s) Call not routed to TGID%s, matching call already active on target: HBSystem: %s, TS: %s, TGID: %s', self._system, int_id(_dst_id), _target, _slot, int_id(_target_status[_slot]['RX_TGID']))
                    continue
                if (_dst_id == _target_status[_slot]['TX_TGID']) and (_rf_src != _target_status[_slot]['TX_RFS']) and ((pkt_time - _target_status[_slot]['TX_TIME']) < STREAM_TO):
                    if self.STATUS[_stream_id]['CONTENTION'] == False:
                        self.STATUS[_stream_id]['CONTENTION'] = True
                        logger.info('(%s) Call not routed for subscriber %s, call route in progress on target: HBSystem: %s, TS: %s, TGID: %s, SUB: %s', self._system, int_id(_rf_src), _target, _slot, int_id(_target_status[_slot]['TX_TGID']), int_id(_target_status[_slot]['TX_RFS']))
                    continue

                # Record target information if this is a new call stream?
                if (_stream_id not in self.STATUS):
                    # Record the DST TGID and Stream ID
                    _target_status[_slot]['TX_START'] = pkt_time
                    _target_status[_slot]['TX_TGID'] = _dst_id
                    _target_status[_slot]['TX_STREAM_ID'] = _stream_id
                    _target_status[_slot]['TX_RFS'] = _rf_src
                    _target_status[_slot]['TX_PEER'] = _peer_id
                    
                    logger.info('(%s) Unit call bridged to HBP System: %s TS: %s, UNIT: %s', self._system, _target, _slot, int_id(_dst_id))
                    if CONFIG['REPORTS']['REPORT']:
                       systems[_target]._report.send_bridgeEvent('UNIT VOICE,START,TX,{},{},{},{},{},{}'.format(_target, int_id(_stream_id), int_id(_peer_id), int_id(_rf_src), _slot, int_id(_dst_id)).encode(encoding='utf-8', errors='ignore'))

                # Set other values for the contention handler to test next time there is a frame to forward
                _target_status[_slot]['TX_TIME'] = pkt_time
                _target_status[_slot]['TX_TYPE'] = _dtype_vseq

            #send the call:
            systems[_target].send_system(_data)
            
            if _target_system['MODE'] == 'OPENBRIDGE':
                if (_frame_type == HBPF_DATA_SYNC) and (_dtype_vseq == HBPF_SLT_VTERM):
                    if (_stream_id in _target_status):
                        _target_status.pop(_stream_id)

        
        # Final actions - Is this a voice terminator?
        if (_frame_type == HBPF_DATA_SYNC) and (_dtype_vseq == HBPF_SLT_VTERM):
            self._targets = []
            call_duration = pkt_time - self.STATUS[_stream_id]['START']
            logger.info('(%s) *UNIT CALL END*   STREAM ID: %s SUB: %s (%s) PEER: %s (%s) UNIT %s (%s), TS %s, Duration: %.2f', \
                    self._system, int_id(_stream_id), get_alias(_rf_src, subscriber_ids), int_id(_rf_src), get_alias(_peer_id, peer_ids), int_id(_peer_id), get_alias(_dst_id, talkgroup_ids), int_id(_dst_id), _slot, call_duration)
            if CONFIG['REPORTS']['REPORT']:
               self._report.send_bridgeEvent('UNIT VOICE,END,RX,{},{},{},{},{},{},{:.2f}'.format(self._system, int_id(_stream_id), int_id(_peer_id), int_id(_rf_src), _slot, int_id(_dst_id), call_duration).encode(encoding='utf-8', errors='ignore'))


    def dmrd_received(self, _peer_id, _rf_src, _dst_id, _seq, _slot, _call_type, _frame_type, _dtype_vseq, _stream_id, _data):

        if _call_type == 'group':
            self.group_received(_peer_id, _rf_src, _dst_id, _seq, _slot, _frame_type, _dtype_vseq, _stream_id, _data)
        elif _call_type == 'unit':
            self.unit_received(_peer_id, _rf_src, _dst_id, _seq, _slot, _frame_type, _dtype_vseq, _stream_id, _data)
        elif _call_type == 'vcsbk':
            self.group_received(_peer_id, _rf_src, _dst_id, _seq, _slot, _frame_type, _dtype_vseq, _stream_id, _data)
            logger.debug('CSBK recieved, forwarded to destination TG.')
        else:
            logger.error('Unknown call type recieved -- not processed')


class routerHBP(HBSYSTEM):
    def __init__(self, _name, _config, _report):
        HBSYSTEM.__init__(self, _name, _config, _report)
##        print(_config)
##        print(HBSYSTEM.dat_test(self))
        self.name = _name

        # list of self._targets for unit (subscriber, private) calls
        self._targets = []

        # Status information for the system, TS1 & TS2
        # 1 & 2 are "timeslot"
        # In TX_EMB_LC, 2-5 are burst B-E
        self.STATUS = {
            1: {
                'RX_START':     time(),
                'TX_START':     time(),
                'RX_SEQ':       0,
                'RX_RFS':       b'\x00',
                'TX_RFS':       b'\x00',
                'RX_PEER':      b'\x00',
                'TX_PEER':      b'\x00',
                'RX_STREAM_ID': b'\x00',
                'TX_STREAM_ID': b'\x00',
                'RX_TGID':      b'\x00\x00\x00',
                'TX_TGID':      b'\x00\x00\x00',
                'RX_TIME':      time(),
                'TX_TIME':      time(),
                'RX_TYPE':      HBPF_SLT_VTERM,
                'TX_TYPE':      HBPF_SLT_VTERM,
                'RX_LC':        b'\x00',
                'TX_H_LC':      b'\x00',
                'TX_T_LC':      b'\x00',
                'TX_EMB_LC': {
                    1: b'\x00',
                    2: b'\x00',
                    3: b'\x00',
                    4: b'\x00',
                    }
                },
            2: {
                'RX_START':     time(),
                'TX_START':     time(),
                'RX_SEQ':       0,
                'RX_RFS':       b'\x00',
                'TX_RFS':       b'\x00',
                'RX_PEER':      b'\x00',
                'TX_PEER':      b'\x00',
                'RX_STREAM_ID': b'\x00',
                'TX_STREAM_ID': b'\x00',
                'RX_TGID':      b'\x00\x00\x00',
                'TX_TGID':      b'\x00\x00\x00',
                'RX_TIME':      time(),
                'TX_TIME':      time(),
                'RX_TYPE':      HBPF_SLT_VTERM,
                'TX_TYPE':      HBPF_SLT_VTERM,
                'RX_LC':        b'\x00',
                'TX_H_LC':      b'\x00',
                'TX_T_LC':      b'\x00',
                'TX_EMB_LC': {
                    1: b'\x00',
                    2: b'\x00',
                    3: b'\x00',
                    4: b'\x00',
                    }
                }
            }
    def group_received(self, _peer_id, _rf_src, _dst_id, _seq, _slot, _frame_type, _dtype_vseq, _stream_id, _data):
        global UNIT_MAP
        pkt_time = time()
        dmrpkt = _data[20:53]
        _bits = _data[15]

        # Make/update an entry in the UNIT_MAP for this subscriber
        UNIT_MAP[_rf_src] = (self.name, pkt_time)

        # Update other servers via OBP
##        svrd_send_all(b'UNIT' + _rf_src) # + b'TIME' + pkt_time)

        # Is this a new call stream?
        if (_stream_id != self.STATUS[_slot]['RX_STREAM_ID']):
            if (self.STATUS[_slot]['RX_TYPE'] != HBPF_SLT_VTERM) and (pkt_time < (self.STATUS[_slot]['RX_TIME'] + STREAM_TO)) and (_rf_src != self.STATUS[_slot]['RX_RFS']):
                logger.warning('(%s) Packet received with STREAM ID: %s <FROM> SUB: %s PEER: %s <TO> TGID %s, SLOT %s collided with existing call', self._system, int_id(_stream_id), int_id(_rf_src), int_id(_peer_id), int_id(_dst_id), _slot)
                return

            # This is a new call stream

            # Send subscriber ID over OBP
            svrd_send_all(b'UNIT' + _rf_src)
            
            self.STATUS[_slot]['RX_START'] = pkt_time
            logger.info('(%s) *GROUP CALL START* STREAM ID: %s SUB: %s (%s) PEER: %s (%s) TGID %s (%s), TS %s', \
                    self._system, int_id(_stream_id), get_alias(_rf_src, subscriber_ids), int_id(_rf_src), get_alias(_peer_id, peer_ids), int_id(_peer_id), get_alias(_dst_id, talkgroup_ids), int_id(_dst_id), _slot)
            if CONFIG['REPORTS']['REPORT']:
                self._report.send_bridgeEvent('GROUP VOICE,START,RX,{},{},{},{},{},{}'.format(self._system, int_id(_stream_id), int_id(_peer_id), int_id(_rf_src), _slot, int_id(_dst_id)).encode(encoding='utf-8', errors='ignore'))

            # If we can, use the LC from the voice header as to keep all options intact
            if _frame_type == HBPF_DATA_SYNC and _dtype_vseq == HBPF_SLT_VHEAD:
                decoded = decode.voice_head_term(dmrpkt)
                self.STATUS[_slot]['RX_LC'] = decoded['LC']

            # If we don't have a voice header then don't wait to decode it from the Embedded LC
            # just make a new one from the HBP header. This is good enough, and it saves lots of time
            else:
                self.STATUS[_slot]['RX_LC'] = LC_OPT + _dst_id + _rf_src
##        # Download rules
##        if _rf_src not in user_rules:
##            user_rules[_rf_src] = self.name
##        if _rf_src in user_rules:
####            print('in')
##            if user_rules[_rf_src] != self.name:
##                user_rules[_rf_src] = self.name
####                print('updated')
####        print(user_rules)
        for _bridge in BRIDGES:
##            print(BRIDGES)
##            print(_bridge)
            # Match bridge name here
            for _system in BRIDGES[_bridge]:
##                print(_system)
                # Modify rule here for indiv system
                if (_system['SYSTEM'] == self._system and _system['TGID'] == _dst_id and _system['TS'] == _slot and _system['ACTIVE'] == True):

                    for _target in BRIDGES[_bridge]:
                        if _target['SYSTEM'] != self._system or (_target['SYSTEM'] == self._system and _target['TS'] != _slot):
                            if _target['ACTIVE']:
                                _target_status = systems[_target['SYSTEM']].STATUS
                                _target_system = self._CONFIG['SYSTEMS'][_target['SYSTEM']]

                                if _target_system['MODE'] == 'OPENBRIDGE':
                                    # Is this a new call stream on the target?
                                    if (_stream_id not in _target_status):
                                        # This is a new call stream on the target
                                        _target_status[_stream_id] = {
                                            'START':     pkt_time,
                                            'CONTENTION':False,
                                            'RFS':       _rf_src,
                                            'TYPE':     'GROUP',
                                            'DST':      _dst_id,
                                            'ACTIVE':   True,
                                        }
                                        # Generate LCs (full and EMB) for the TX stream
                                        dst_lc = b''.join([self.STATUS[_slot]['RX_LC'][0:3], _target['TGID'], _rf_src])
                                        _target_status[_stream_id]['H_LC'] = bptc.encode_header_lc(dst_lc)
                                        _target_status[_stream_id]['T_LC'] = bptc.encode_terminator_lc(dst_lc)
                                        _target_status[_stream_id]['EMB_LC'] = bptc.encode_emblc(dst_lc)

                                        logger.info('(%s) Conference Bridge: %s, Call Bridged to OBP System: %s TS: %s, TGID: %s', self._system, _bridge, _target['SYSTEM'], _target['TS'], int_id(_target['TGID']))
                                        if CONFIG['REPORTS']['REPORT']:
                                            systems[_target['SYSTEM']]._report.send_bridgeEvent('GROUP VOICE,START,TX,{},{},{},{},{},{}'.format(_target['SYSTEM'], int_id(_stream_id), int_id(_peer_id), int_id(_rf_src), _target['TS'], int_id(_target['TGID'])).encode(encoding='utf-8', errors='ignore'))

                                    # Record the time of this packet so we can later identify a stale stream
                                    _target_status[_stream_id]['LAST'] = pkt_time
                                    # Clear the TS bit -- all OpenBridge streams are effectively on TS1
                                    _tmp_bits = _bits & ~(1 << 7)

                                    # Assemble transmit HBP packet header
                                    _tmp_data = b''.join([_data[:8], _target['TGID'], _data[11:15], _tmp_bits.to_bytes(1, 'big'), _data[16:20]])

                                    # MUST TEST FOR NEW STREAM AND IF SO, RE-WRITE THE LC FOR THE TARGET
                                    # MUST RE-WRITE DESTINATION TGID IF DIFFERENT
                                    # if _dst_id != rule['DST_GROUP']:
                                    dmrbits = bitarray(endian='big')
                                    dmrbits.frombytes(dmrpkt)
                                    # Create a voice header packet (FULL LC)
                                    if _frame_type == HBPF_DATA_SYNC and _dtype_vseq == HBPF_SLT_VHEAD:
                                        dmrbits = _target_status[_stream_id]['H_LC'][0:98] + dmrbits[98:166] + _target_status[_stream_id]['H_LC'][98:197]
                                    # Create a voice terminator packet (FULL LC)
                                    elif _frame_type == HBPF_DATA_SYNC and _dtype_vseq == HBPF_SLT_VTERM:
                                        dmrbits = _target_status[_stream_id]['T_LC'][0:98] + dmrbits[98:166] + _target_status[_stream_id]['T_LC'][98:197]
                                        if CONFIG['REPORTS']['REPORT']:
                                            call_duration = pkt_time - _target_status[_stream_id]['START']
                                            _target_status[_stream_id]['ACTIVE'] = False
                                            systems[_target['SYSTEM']]._report.send_bridgeEvent('GROUP VOICE,END,TX,{},{},{},{},{},{},{:.2f}'.format(_target['SYSTEM'], int_id(_stream_id), int_id(_peer_id), int_id(_rf_src), _target['TS'], int_id(_target['TGID']), call_duration).encode(encoding='utf-8', errors='ignore'))
                                    # Create a Burst B-E packet (Embedded LC)
                                    elif _dtype_vseq in [1,2,3,4]:
                                        dmrbits = dmrbits[0:116] + _target_status[_stream_id]['EMB_LC'][_dtype_vseq] + dmrbits[148:264]
                                    dmrpkt = dmrbits.tobytes()
                                    _tmp_data = b''.join([_tmp_data, dmrpkt])

                                else:
                                    # BEGIN STANDARD CONTENTION HANDLING
                                    #
                                    # The rules for each of the 4 "ifs" below are listed here for readability. The Frame To Send is:
                                    #   From a different group than last RX from this HBSystem, but it has been less than Group Hangtime
                                    #   From a different group than last TX to this HBSystem, but it has been less than Group Hangtime
                                    #   From the same group as the last RX from this HBSystem, but from a different subscriber, and it has been less than stream timeout
                                    #   From the same group as the last TX to this HBSystem, but from a different subscriber, and it has been less than stream timeout
                                    # The "continue" at the end of each means the next iteration of the for loop that tests for matching rules
                                    #
                                    if ((_target['TGID'] != _target_status[_target['TS']]['RX_TGID']) and ((pkt_time - _target_status[_target['TS']]['RX_TIME']) < _target_system['GROUP_HANGTIME'])):
                                        if _frame_type == HBPF_DATA_SYNC and _dtype_vseq == HBPF_SLT_VHEAD and self.STATUS[_slot]['RX_STREAM_ID'] != _stream_id:
                                            logger.info('(%s) Call not routed to TGID %s, target active or in group hangtime: HBSystem: %s, TS: %s, TGID: %s', self._system, int_id(_target['TGID']), _target['SYSTEM'], _target['TS'], int_id(_target_status[_target['TS']]['RX_TGID']))
                                        continue
                                    if ((_target['TGID'] != _target_status[_target['TS']]['TX_TGID']) and ((pkt_time - _target_status[_target['TS']]['TX_TIME']) < _target_system['GROUP_HANGTIME'])):
                                        if _frame_type == HBPF_DATA_SYNC and _dtype_vseq == HBPF_SLT_VHEAD and self.STATUS[_slot]['RX_STREAM_ID'] != _stream_id:
                                            logger.info('(%s) Call not routed to TGID%s, target in group hangtime: HBSystem: %s, TS: %s, TGID: %s', self._system, int_id(_target['TGID']), _target['SYSTEM'], _target['TS'], int_id(_target_status[_target['TS']]['TX_TGID']))
                                        continue
                                    if (_target['TGID'] == _target_status[_target['TS']]['RX_TGID']) and ((pkt_time - _target_status[_target['TS']]['RX_TIME']) < STREAM_TO):
                                        if _frame_type == HBPF_DATA_SYNC and _dtype_vseq == HBPF_SLT_VHEAD and self.STATUS[_slot]['RX_STREAM_ID'] != _stream_id:
                                            logger.info('(%s) Call not routed to TGID%s, matching call already active on target: HBSystem: %s, TS: %s, TGID: %s', self._system, int_id(_target['TGID']), _target['SYSTEM'], _target['TS'], int_id(_target_status[_target['TS']]['RX_TGID']))
                                        continue
                                    if (_target['TGID'] == _target_status[_target['TS']]['TX_TGID']) and (_rf_src != _target_status[_target['TS']]['TX_RFS']) and ((pkt_time - _target_status[_target['TS']]['TX_TIME']) < STREAM_TO):
                                        if _frame_type == HBPF_DATA_SYNC and _dtype_vseq == HBPF_SLT_VHEAD and self.STATUS[_slot]['RX_STREAM_ID'] != _stream_id:
                                            logger.info('(%s) Call not routed for subscriber %s, call route in progress on target: HBSystem: %s, TS: %s, TGID: %s, SUB: %s', self._system, int_id(_rf_src), _target['SYSTEM'], _target['TS'], int_id(_target_status[_target['TS']]['TX_TGID']), int_id(_target_status[_target['TS']]['TX_RFS']))
                                        continue

                                    # Is this a new call stream?
                                    if (_stream_id != self.STATUS[_slot]['RX_STREAM_ID']):
                                        # Record the DST TGID and Stream ID
                                        _target_status[_target['TS']]['TX_START'] = pkt_time
                                        _target_status[_target['TS']]['TX_TGID'] = _target['TGID']
                                        _target_status[_target['TS']]['TX_STREAM_ID'] = _stream_id
                                        _target_status[_target['TS']]['TX_RFS'] = _rf_src
                                        _target_status[_target['TS']]['TX_PEER'] = _peer_id
                                        # Generate LCs (full and EMB) for the TX stream
                                        dst_lc = self.STATUS[_slot]['RX_LC'][0:3] + _target['TGID'] + _rf_src
                                        _target_status[_target['TS']]['TX_H_LC'] = bptc.encode_header_lc(dst_lc)
                                        _target_status[_target['TS']]['TX_T_LC'] = bptc.encode_terminator_lc(dst_lc)
                                        _target_status[_target['TS']]['TX_EMB_LC'] = bptc.encode_emblc(dst_lc)
                                        logger.debug('(%s) Generating TX FULL and EMB LCs for HomeBrew destination: System: %s, TS: %s, TGID: %s', self._system, _target['SYSTEM'], _target['TS'], int_id(_target['TGID']))
                                        logger.info('(%s) Conference Bridge: %s, Call Bridged to HBP System: %s TS: %s, TGID: %s', self._system, _bridge, _target['SYSTEM'], _target['TS'], int_id(_target['TGID']))
                                        if CONFIG['REPORTS']['REPORT']:
                                            systems[_target['SYSTEM']]._report.send_bridgeEvent('GROUP VOICE,START,TX,{},{},{},{},{},{}'.format(_target['SYSTEM'], int_id(_stream_id), int_id(_peer_id), int_id(_rf_src), _target['TS'], int_id(_target['TGID'])).encode(encoding='utf-8', errors='ignore'))

                                    # Set other values for the contention handler to test next time there is a frame to forward
                                    _target_status[_target['TS']]['TX_TIME'] = pkt_time
                                    _target_status[_target['TS']]['TX_TYPE'] = _dtype_vseq

                                    # Handle any necessary re-writes for the destination
                                    if _system['TS'] != _target['TS']:
                                        _tmp_bits = _bits ^ 1 << 7
                                    else:
                                        _tmp_bits = _bits

                                    # Assemble transmit HBP packet header
                                    _tmp_data = b''.join([_data[:8], _target['TGID'], _data[11:15], _tmp_bits.to_bytes(1, 'big'), _data[16:20]])

                                    dmrbits = bitarray(endian='big')
                                    dmrbits.frombytes(dmrpkt)
                                    # Create a voice header packet (FULL LC)
                                    if _frame_type == HBPF_DATA_SYNC and _dtype_vseq == HBPF_SLT_VHEAD:
                                        dmrbits = _target_status[_target['TS']]['TX_H_LC'][0:98] + dmrbits[98:166] + _target_status[_target['TS']]['TX_H_LC'][98:197]
                                    # Create a voice terminator packet (FULL LC)
                                    elif _frame_type == HBPF_DATA_SYNC and _dtype_vseq == HBPF_SLT_VTERM:
                                        dmrbits = _target_status[_target['TS']]['TX_T_LC'][0:98] + dmrbits[98:166] + _target_status[_target['TS']]['TX_T_LC'][98:197]
                                        if CONFIG['REPORTS']['REPORT']:
                                            call_duration = pkt_time - _target_status[_target['TS']]['TX_START']
                                            systems[_target['SYSTEM']]._report.send_bridgeEvent('GROUP VOICE,END,TX,{},{},{},{},{},{},{:.2f}'.format(_target['SYSTEM'], int_id(_stream_id), int_id(_peer_id), int_id(_rf_src), _target['TS'], int_id(_target['TGID']), call_duration).encode(encoding='utf-8', errors='ignore'))
                                    # Create a Burst B-E packet (Embedded LC)
                                    elif _dtype_vseq in [1,2,3,4]:
                                        dmrbits = dmrbits[0:116] + _target_status[_target['TS']]['TX_EMB_LC'][_dtype_vseq] + dmrbits[148:264]
                                    dmrpkt = dmrbits.tobytes()
                                    _tmp_data = b''.join([_tmp_data, dmrpkt, _data[53:55]])

                                # Transmit the packet to the destination system
                                systems[_target['SYSTEM']].send_system(_tmp_data)
                                #logger.debug('(%s) Packet routed by bridge: %s to system: %s TS: %s, TGID: %s', self._system, _bridge, _target['SYSTEM'], _target['TS'], int_id(_target['TGID']))
                                
                                if _target_system['MODE'] == 'OPENBRIDGE':
                                    if (_frame_type == HBPF_DATA_SYNC) and (_dtype_vseq == HBPF_SLT_VTERM) and (self.STATUS[_slot]['RX_TYPE'] != HBPF_SLT_VTERM):
                                        if (_stream_id in _target_status):
                                            _target_status.pop(_stream_id)


        # Final actions - Is this a voice terminator?
        if (_frame_type == HBPF_DATA_SYNC) and (_dtype_vseq == HBPF_SLT_VTERM) and (self.STATUS[_slot]['RX_TYPE'] != HBPF_SLT_VTERM):
            call_duration = pkt_time - self.STATUS[_slot]['RX_START']
            logger.info('(%s) *GROUP CALL END*   STREAM ID: %s SUB: %s (%s) PEER: %s (%s) TGID %s (%s), TS %s, Duration: %.2f', \
                    self._system, int_id(_stream_id), get_alias(_rf_src, subscriber_ids), int_id(_rf_src), get_alias(_peer_id, peer_ids), int_id(_peer_id), get_alias(_dst_id, talkgroup_ids), int_id(_dst_id), _slot, call_duration)
            if CONFIG['REPORTS']['REPORT']:
               self._report.send_bridgeEvent('GROUP VOICE,END,RX,{},{},{},{},{},{},{:.2f}'.format(self._system, int_id(_stream_id), int_id(_peer_id), int_id(_rf_src), _slot, int_id(_dst_id), call_duration).encode(encoding='utf-8', errors='ignore'))

            #
            # Begin in-band signalling for call end. This has nothign to do with routing traffic directly.
            #

            # Iterate the rules dictionary

            for _bridge in BRIDGES:
                for _system in BRIDGES[_bridge]:
                    if _system['SYSTEM'] == self._system:
##                        # Insert POST for TG timer update?
##                        print(_system)
##                        print()
##                        print(datetime.fromtimestamp(_system['TIMER']).strftime('%H:%M:%S - %m/%d/%y'))

                        # TGID matches a rule source, reset its timer
                        if _slot == _system['TS'] and _dst_id == _system['TGID'] and ((_system['TO_TYPE'] == 'ON' and (_system['ACTIVE'] == True)) or (_system['TO_TYPE'] == 'OFF' and _system['ACTIVE'] == False)):
                            _system['TIMER'] = pkt_time + _system['TIMEOUT']
                            logger.info('(%s) Transmission match for Bridge: %s. Reset timeout to %s', self._system, _bridge, _system['TIMER'])

                        # TGID matches an ACTIVATION trigger
                        if (_dst_id in _system['ON'] or _dst_id in _system['RESET']) and _slot == _system['TS']:
                            # POST update TG for self care
                            #update_tg(CONFIG, 'on', int(str(int_id(self.STATUS[2]['RX_PEER']))[:7]), [{'SYSTEM':_system['SYSTEM']}, {'ts1':int_id(self.STATUS[1]['RX_TGID'])}, {'ts2':int_id(self.STATUS[2]['RX_TGID'])}])
##                            print(datetime.fromtimestamp(_system['TIMER']).strftime('%H:%M:%S - %m/%d/%y'))

##                            update_tg(CONFIG, mode, dmr_id, data)
                            # Set the matching rule as ACTIVE
                            if _dst_id in _system['ON']:
                                if _system['ACTIVE'] == False:
                                    _system['ACTIVE'] = True
                                    _system['TIMER'] = pkt_time + _system['TIMEOUT']

                                    logger.info('(%s) Bridge: %s, connection changed to state: %s', self._system, _bridge, _system['ACTIVE'])
                                    # Cancel the timer if we've enabled an "OFF" type timeout
                                    if _system['TO_TYPE'] == 'OFF':
                                        _system['TIMER'] = pkt_time
                                        logger.info('(%s) Bridge: %s set to "OFF" with an on timer rule: timeout timer cancelled', self._system, _bridge)
                            # Reset the timer for the rule
                            if _system['ACTIVE'] == True and _system['TO_TYPE'] == 'ON':
                                _system['TIMER'] = pkt_time + _system['TIMEOUT']
                                logger.info('(%s) Bridge: %s, timeout timer reset to: %s', self._system, _bridge, _system['TIMER'] - pkt_time)

                        # TGID matches an DE-ACTIVATION trigger
                        if (_dst_id in _system['OFF']  or _dst_id in _system['RESET']) and _slot == _system['TS']:
                            # Set the matching rule as ACTIVE
                            if _dst_id in _system['OFF']:
                                if _system['ACTIVE'] == True:
                                    _system['ACTIVE'] = False
                                    logger.info('(%s) Bridge: %s, connection changed to state: %s', self._system, _bridge, _system['ACTIVE'])
                                    # POST off
                                    #update_tg(CONFIG, 'off', 0, [{'SYSTEM':_system['SYSTEM']}, {'ts':_system['TS']}, {'tg': int_id(_system['TGID'])}])
##                                    update_tg(CONFIG, 'on', int(str(int_id(self.STATUS[2]['RX_PEER']))[:7]), [{'SYSTEM':_system['SYSTEM']}, {'ts1':int_id(self.STATUS[1]['RX_TGID'])}, {'ts2':int_id(self.STATUS[2]['RX_TGID'])}])
                                    # Cancel the timer if we've enabled an "ON" type timeout
                                    if _system['TO_TYPE'] == 'ON':
                                        _system['TIMER'] = pkt_time
                                        logger.info('(%s) Bridge: %s set to ON with and "OFF" timer rule: timeout timer cancelled', self._system, _bridge)
                            # Reset the timer for the rule
                            if _system['ACTIVE'] == False and _system['TO_TYPE'] == 'OFF':
                                _system['TIMER'] = pkt_time + _system['TIMEOUT']
                                logger.info('(%s) Bridge: %s, timeout timer reset to: %s', self._system, _bridge, _system['TIMER'] - pkt_time)
                            # Cancel the timer if we've enabled an "ON" type timeout
                            if _system['ACTIVE'] == True and _system['TO_TYPE'] == 'ON' and _dst_group in _system['OFF']:
                                _system['TIMER'] = pkt_time
                                logger.info('(%s) Bridge: %s set to ON with and "OFF" timer rule: timeout timer cancelled', self._system, _bridge)

        #
        # END IN-BAND SIGNALLING
        #
        # Mark status variables for use later
        self.STATUS[_slot]['RX_PEER']      = _peer_id
        self.STATUS[_slot]['RX_SEQ']       = _seq
        self.STATUS[_slot]['RX_RFS']       = _rf_src
        self.STATUS[_slot]['RX_TYPE']      = _dtype_vseq
        self.STATUS[_slot]['RX_TGID']      = _dst_id
        self.STATUS[_slot]['RX_TIME']      = pkt_time
        self.STATUS[_slot]['RX_STREAM_ID'] = _stream_id


    def unit_received(self, _peer_id, _rf_src, _dst_id, _seq, _slot, _frame_type, _dtype_vseq, _stream_id, _data):
        global UNIT_MAP
        pkt_time = time()
        dmrpkt = _data[20:53]
        _bits = _data[15]
 
        # Make/update this unit in the UNIT_MAP cache
        UNIT_MAP[_rf_src] = (self.name, pkt_time)

        # Update other servers via OBP
##        svrd_send_all(b'UNIT' + _rf_src) # + b'TIME' + pkt_time)
        
        
        # Is this a new call stream?
        svrd_send_all(b'UNIT' + _rf_src)
        
        if (_stream_id != self.STATUS[_slot]['RX_STREAM_ID']):
            
            # Collision in progress, bail out!
            if (self.STATUS[_slot]['RX_TYPE'] != HBPF_SLT_VTERM) and (pkt_time < (self.STATUS[_slot]['RX_TIME'] + STREAM_TO)) and (_rf_src != self.STATUS[_slot]['RX_RFS']):
                logger.warning('(%s) Packet received with STREAM ID: %s <FROM> SUB: %s PEER: %s <TO> UNIT %s, SLOT %s collided with existing call', self._system, int_id(_stream_id), int_id(_rf_src), int_id(_peer_id), int_id(_dst_id), _slot)
                return
                
            # Create a destination list for the call:
            if _dst_id in UNIT_MAP:
                if UNIT_MAP[_dst_id][0] != self._system:
                    self._targets = [UNIT_MAP[_dst_id][0]]
                else:
                    self._targets = []
                    logger.error('UNIT call to a subscriber on the same system, send nothing')
            else:
                self._targets = list(UNIT)
                self._targets.remove(self._system)
            
            # This is a new call stream, so log & report
            svrd_send_all(b'UNIT' + _rf_src)
            self.STATUS[_slot]['RX_START'] = pkt_time
            logger.info('(%s) *UNIT CALL START* STREAM ID: %s SUB: %s (%s) PEER: %s (%s) UNIT: %s (%s), TS: %s, FORWARD: %s', \
                    self._system, int_id(_stream_id), get_alias(_rf_src, subscriber_ids), int_id(_rf_src), get_alias(_peer_id, peer_ids), int_id(_peer_id), get_alias(_dst_id, talkgroup_ids), int_id(_dst_id), _slot, self._targets)
            if CONFIG['REPORTS']['REPORT']:
                self._report.send_bridgeEvent('UNIT VOICE,START,RX,{},{},{},{},{},{},{}'.format(self._system, int_id(_stream_id), int_id(_peer_id), int_id(_rf_src), _slot, int_id(_dst_id), self._targets).encode(encoding='utf-8', errors='ignore'))

        for _target in self._targets:
                
            _target_status = systems[_target].STATUS
            _target_system = self._CONFIG['SYSTEMS'][_target]
            
            if self._CONFIG['SYSTEMS'][_target]['MODE'] == 'OPENBRIDGE':
                if (_stream_id not in _target_status):
                    # This is a new call stream on the target
                    _target_status[_stream_id] = {
                        'START':     pkt_time,
                        'CONTENTION':False,
                        'RFS':       _rf_src,
                        'TYPE':      'UNIT',
                        'DST':      _dst_id,
                        'ACTIVE':   True
                    }

                    logger.info('(%s) Unit call bridged to OBP System: %s TS: %s, UNIT: %s', self._system, _target, _slot if _target_system['BOTH_SLOTS'] else 1, int_id(_dst_id))
                    if CONFIG['REPORTS']['REPORT']:
                        systems[_target]._report.send_bridgeEvent('UNIT VOICE,START,TX,{},{},{},{},{},{}'.format(_target, int_id(_stream_id), int_id(_peer_id), int_id(_rf_src), _slot, int_id(_dst_id)).encode(encoding='utf-8', errors='ignore'))

                # Record the time of this packet so we can later identify a stale stream
                _target_status[_stream_id]['LAST'] = pkt_time
                # Clear the TS bit and follow propper OBP definition, unless "BOTH_SLOTS" is set. This only works for unit calls.
                if _target_system['BOTH_SLOTS']:
                    _tmp_bits = _bits
                else:
                    _tmp_bits = _bits & ~(1 << 7)

                # Assemble transmit HBP packet
                _tmp_data = b''.join([_data[:15], _tmp_bits.to_bytes(1, 'big'), _data[16:20]])
                _data = b''.join([_tmp_data, dmrpkt])
                
                if (_frame_type == HBPF_DATA_SYNC) and (_dtype_vseq == HBPF_SLT_VTERM):
                    _target_status[_stream_id]['ACTIVE'] = False

            else:
                # BEGIN STANDARD CONTENTION HANDLING
                #
                # The rules for each of the 4 "ifs" below are listed here for readability. The Frame To Send is:
                #   From a different group than last RX from this HBSystem, but it has been less than Group Hangtime
                #   From a different group than last TX to this HBSystem, but it has been less than Group Hangtime
                #   From the same group as the last RX from this HBSystem, but from a different subscriber, and it has been less than stream timeout
                #   From the same group as the last TX to this HBSystem, but from a different subscriber, and it has been less than stream timeout
                # The "continue" at the end of each means the next iteration of the for loop that tests for matching rules
                #
                '''
                if ((_dst_id != _target_status[_slot]['RX_TGID']) and ((pkt_time - _target_status[_slot]['RX_TIME']) < _target_system['GROUP_HANGTIME'])):
                    if _frame_type == HBPF_DATA_SYNC and _dtype_vseq == HBPF_SLT_VHEAD and self.STATUS[_slot]['RX_STREAM_ID'] != _stream_id:
                        logger.info('(%s) Call not routed to destination %s, target active or in group hangtime: HBSystem: %s, TS: %s, DEST: %s', self._system, int_id(_dst_id), _target, _slot, int_id(_target_status[_slot]['RX_TGID']))
                    continue
                if ((_dst_id != _target_status[_slot]['TX_TGID']) and ((pkt_time - _target_status[_slot]['TX_TIME']) < _target_system['GROUP_HANGTIME'])):
                    if _frame_type == HBPF_DATA_SYNC and _dtype_vseq == HBPF_SLT_VHEAD and self.STATUS[_slot]['RX_STREAM_ID'] != _stream_id:
                        logger.info('(%s) Call not routed to destination %s, target in group hangtime: HBSystem: %s, TS: %s, DEST: %s', self._system, int_id(_dst_id), _target, _slot, int_id(_target_status[_slot]['TX_TGID']))
                    continue
                '''
                if (_dst_id == _target_status[_slot]['RX_TGID']) and ((pkt_time - _target_status[_slot]['RX_TIME']) < STREAM_TO):
                    if _frame_type == HBPF_DATA_SYNC and _dtype_vseq == HBPF_SLT_VHEAD and self.STATUS[_slot]['RX_STREAM_ID'] != _stream_id:
                        logger.info('(%s) Call not routed to destination %s, matching call already active on target: HBSystem: %s, TS: %s, DEST: %s', self._system, int_id(_dst_id), _target, _slot, int_id(_target_status[_slot]['RX_TGID']))
                    continue
                if (_dst_id == _target_status[_slot]['TX_TGID']) and (_rf_src != _target_status[_slot]['TX_RFS']) and ((pkt_time - _target_status[_slot]['TX_TIME']) < STREAM_TO):
                    if _frame_type == HBPF_DATA_SYNC and _dtype_vseq == HBPF_SLT_VHEAD and self.STATUS[_slot]['RX_STREAM_ID'] != _stream_id:
                        logger.info('(%s) Call not routed for subscriber %s, call route in progress on target: HBSystem: %s, TS: %s, DEST: %s, SUB: %s', self._system, int_id(_rf_src), _target, _slot, int_id(_target_status[_slot]['TX_TGID']), int_id(_target_status[_slot]['TX_RFS']))
                    continue

                # Record target information if this is a new call stream?
                if (_stream_id != self.STATUS[_slot]['RX_STREAM_ID']):
                    # Record the DST TGID and Stream ID
                    _target_status[_slot]['TX_START'] = pkt_time
                    _target_status[_slot]['TX_TGID'] = _dst_id
                    _target_status[_slot]['TX_STREAM_ID'] = _stream_id
                    _target_status[_slot]['TX_RFS'] = _rf_src
                    _target_status[_slot]['TX_PEER'] = _peer_id
                    
                    logger.info('(%s) Unit call bridged to HBP System: %s TS: %s, UNIT: %s', self._system, _target, _slot, int_id(_dst_id))
                    if CONFIG['REPORTS']['REPORT']:
                       systems[_target]._report.send_bridgeEvent('UNIT VOICE,START,TX,{},{},{},{},{},{}'.format(_target, int_id(_stream_id), int_id(_peer_id), int_id(_rf_src), _slot, int_id(_dst_id)).encode(encoding='utf-8', errors='ignore'))

                # Set other values for the contention handler to test next time there is a frame to forward
                _target_status[_slot]['TX_TIME'] = pkt_time
                _target_status[_slot]['TX_TYPE'] = _dtype_vseq

            #send the call:
            systems[_target].send_system(_data)
                        
        
        # Final actions - Is this a voice terminator?
        if (_frame_type == HBPF_DATA_SYNC) and (_dtype_vseq == HBPF_SLT_VTERM) and (self.STATUS[_slot]['RX_TYPE'] != HBPF_SLT_VTERM):
            self._targets = []
            call_duration = pkt_time - self.STATUS[_slot]['RX_START']
            logger.info('(%s) *UNIT CALL END*   STREAM ID: %s SUB: %s (%s) PEER: %s (%s) UNIT %s (%s), TS %s, Duration: %.2f', \
                    self._system, int_id(_stream_id), get_alias(_rf_src, subscriber_ids), int_id(_rf_src), get_alias(_peer_id, peer_ids), int_id(_peer_id), get_alias(_dst_id, talkgroup_ids), int_id(_dst_id), _slot, call_duration)
            if CONFIG['REPORTS']['REPORT']:
               self._report.send_bridgeEvent('UNIT VOICE,END,RX,{},{},{},{},{},{},{:.2f}'.format(self._system, int_id(_stream_id), int_id(_peer_id), int_id(_rf_src), _slot, int_id(_dst_id), call_duration).encode(encoding='utf-8', errors='ignore'))

        # Mark status variables for use later
        self.STATUS[_slot]['RX_PEER']      = _peer_id
        self.STATUS[_slot]['RX_SEQ']       = _seq
        self.STATUS[_slot]['RX_RFS']       = _rf_src
        self.STATUS[_slot]['RX_TYPE']      = _dtype_vseq
        self.STATUS[_slot]['RX_TGID']      = _dst_id
        self.STATUS[_slot]['RX_TIME']      = pkt_time
        self.STATUS[_slot]['RX_STREAM_ID'] = _stream_id

    def dmrd_received(self, _peer_id, _rf_src, _dst_id, _seq, _slot, _call_type, _frame_type, _dtype_vseq, _stream_id, _data):
        if _call_type == 'group':
            self.group_received(_peer_id, _rf_src, _dst_id, _seq, _slot, _frame_type, _dtype_vseq, _stream_id, _data)
            mirror_traffic(_data)
            expose_all(_data)
        elif _call_type == 'unit':
            if self._system not in UNIT:
                logger.error('(%s) *UNIT CALL NOT FORWARDED* UNIT calling is disabled for this system (INGRESS)', self._system)
            else:
                self.unit_received(_peer_id, _rf_src, _dst_id, _seq, _slot, _frame_type, _dtype_vseq, _stream_id, _data)
                mirror_traffic(_data)
                expose_all(_data)
        elif _call_type == 'vcsbk':
            self.group_received(_peer_id, _rf_src, _dst_id, _seq, _slot, _frame_type, _dtype_vseq, _stream_id, _data)
            logger.debug('CSBK recieved, forwarded to destination TG.')
            mirror_traffic(_data)
            expose_all(_data)
        else:
            logger.error('Unknown call type recieved -- not processed')
            mirror_traffic(_data)
            expose_all(_data)

#
# Socket-based reporting section
#
class bridgeReportFactory(reportFactory):

    def send_bridge(self):
        serialized = pickle.dumps(BRIDGES, protocol=2) #.decode("utf-8", errors='ignore')
        self.send_clients(REPORT_OPCODES['BRIDGE_SND']+serialized)

    def send_bridgeEvent(self, _data):
        if isinstance(_data, str):
            _data = _data.decode('utf-8', error='ignore')
        self.send_clients(REPORT_OPCODES['BRDG_EVENT']+_data)


#************************************************
#      MAIN PROGRAM LOOP STARTS HERE
#************************************************

if __name__ == '__main__':

    import argparse
    import sys
    import os
    import signal

##    global unit_flood_time

    # Change the current directory to the location of the application
    os.chdir(os.path.dirname(os.path.realpath(sys.argv[0])))

    # CLI argument parser - handles picking up the config file from the command line, and sending a "help" message
    parser = argparse.ArgumentParser()
    parser.add_argument('-c', '--config', action='store', dest='CONFIG_FILE', help='/full/path/to/config.file (usually hbnet.cfg)')
    parser.add_argument('-r', '--rules', action='store', dest='RULES_FILE', help='/full/path/to/rules.file (usually rules.py)')
    parser.add_argument('-l', '--logging', action='store', dest='LOG_LEVEL', help='Override config file logging level.')
    cli_args = parser.parse_args()

    # Ensure we have a path for the config file, if one wasn't specified, then use the default (top of file)
    if not cli_args.CONFIG_FILE:
        cli_args.CONFIG_FILE = os.path.dirname(os.path.abspath(__file__))+'/hbnet.cfg'

    # Call the external routine to build the configuration dictionary
    LOCAL_CONFIG = config.build_config(cli_args.CONFIG_FILE)
    if LOCAL_CONFIG['WEB_SERVICE']['REMOTE_CONFIG_ENABLED']:
        CONFIG = download_config(LOCAL_CONFIG, cli_args.CONFIG_FILE)
##        print(CONFIG['SYSTEMS'])
##        print('enabled')
    else:
        CONFIG = config.build_config(cli_args.CONFIG_FILE)

    # Ensure we have a path for the rules file, if one wasn't specified, then use the default (top of file)
    if not cli_args.RULES_FILE:
        cli_args.RULES_FILE = os.path.dirname(os.path.abspath(__file__))+'/rules.py'

    # Start the system logger
    if cli_args.LOG_LEVEL:
        CONFIG['LOGGER']['LOG_LEVEL'] = cli_args.LOG_LEVEL
    logger = log.config_logging(CONFIG['LOGGER'])
    logger.info('\n\nCopyright (c) 2020, 2021, 2022\n\tKF7EEL - Eric, kf7eel@qsl.net -  All rights reserved.\n')
    logger.info('\n\nCopyright (c) 2013, 2014, 2015, 2016, 2018, 2019, 2020\n\tThe Regents of the K0USY Group. All rights reserved.\n')
    logger.debug('(GLOBAL) Logging system started, anything from here on gets logged')

    # Set up the signal handler
    def sig_handler(_signal, _frame):
        logger.info('(GLOBAL) SHUTDOWN: CONFBRIDGE IS TERMINATING WITH SIGNAL %s', str(_signal))
        hblink_handler(_signal, _frame)
        logger.info('(GLOBAL) SHUTDOWN: ALL SYSTEM HANDLERS EXECUTED - STOPPING REACTOR')
        os.popen('rm /tmp/' + (CONFIG['LOGGER']['LOG_NAME'] + '_PEERS/*'))
        reactor.stop()

    # Set signal handers so that we can gracefully exit if need be
    for sig in [signal.SIGINT, signal.SIGTERM]:
        signal.signal(sig, sig_handler)

    # Create the name-number mapping dictionaries
    peer_ids, subscriber_ids, talkgroup_ids = mk_aliases(CONFIG)
    

    # INITIALIZE THE REPORTING LOOP
    if CONFIG['REPORTS']['REPORT']:
        report_server = config_reports(CONFIG, bridgeReportFactory)
    else:
        report_server = None
        logger.info('(REPORT) TCP Socket reporting not configured')

    # HBlink instance creation
    logger.info('(GLOBAL) HBNet \'hbnet.py\' -- SYSTEM STARTING...')

    # Generate list of Enabled MODE: PROXY masters
    proxy_master_list = []
    for i in CONFIG['SYSTEMS']:
        if CONFIG['SYSTEMS'][i]['ENABLED'] == True:
            if CONFIG['SYSTEMS'][i]['MODE'] == 'PROXY':
                proxy_master_list.append(i)
    # Start proxy as a thread (if enabled in config) for each set of MASTERs
    for m in proxy_master_list:
        if CONFIG['SYSTEMS'][m]['EXTERNAL_PROXY_SCRIPT'] == False:
            proxy_thread = threading.Thread(target=hotspot_proxy, args=(CONFIG['SYSTEMS'][m]['EXTERNAL_PORT'],CONFIG['SYSTEMS'][m]['INTERNAL_PORT_START'],CONFIG['SYSTEMS'][m]['INTERNAL_PORT_STOP'],))
            proxy_thread.daemon = True
            proxy_thread.start()
            logger.info('Started thread for PROXY for MASTER set: ' + m)
                
    #Build Master configs from list
    for i in proxy_master_list:
        n_systems = CONFIG['SYSTEMS'][i]['INTERNAL_PORT_STOP'] - CONFIG['SYSTEMS'][i]['INTERNAL_PORT_START']
        n_count = 0
        while n_count < n_systems:
            CONFIG['SYSTEMS'].update({i + '-' + str(n_count): {
            'MODE': 'MASTER',
            'ENABLED': True,
            'STATIC_APRS_POSITION_ENABLED': CONFIG['SYSTEMS'][i]['STATIC_APRS_POSITION_ENABLED'],
            'USE_USER_MAN': CONFIG['SYSTEMS'][i]['USE_USER_MAN'],
            'REPEAT': CONFIG['SYSTEMS'][i]['REPEAT'],
            'MAX_PEERS': 1,
            'IP': '127.0.0.1',
            'PORT': CONFIG['SYSTEMS'][i]['INTERNAL_PORT_START'] + n_count,
            'PASSPHRASE': CONFIG['SYSTEMS'][i]['PASSPHRASE'],
            'GROUP_HANGTIME': CONFIG['SYSTEMS'][i]['GROUP_HANGTIME'],
            'USE_ACL': CONFIG['SYSTEMS'][i]['USE_ACL'],
            'REG_ACL': CONFIG['SYSTEMS'][i]['REG_ACL'],
            'SUB_ACL': CONFIG['SYSTEMS'][i]['SUB_ACL'],
            'TG1_ACL': CONFIG['SYSTEMS'][i]['TG1_ACL'],
            'TG2_ACL': CONFIG['SYSTEMS'][i]['TG2_ACL']
            }})
            CONFIG['SYSTEMS'][i + '-' + str(n_count)].update({'PEERS': {}})
            systems[i + '-' + str(n_count)] = routerHBP(i + '-' + str(n_count), CONFIG, report_server)
            n_count = n_count + 1
        # Remove original MASTER stanza to prevent errors
        CONFIG['SYSTEMS'].pop(i)
        logger.info('Generated MASTER instances for proxy set: ' + i)

    # Attempt to use downloaded rules    
    if LOCAL_CONFIG['WEB_SERVICE']['REMOTE_CONFIG_ENABLED']:
        try:
            remote_config = download_rules(LOCAL_CONFIG, cli_args.CONFIG_FILE)
            # Build the routing rules file
            BRIDGES = make_bridges(remote_config[1], True) #make_bridges(rules_module.BRIDGES)
            # Get rule parameter for private calls
            UNIT = remote_config[0]
            unit_flood_time = CONFIG['OTHER']['UNIT_TIME']
        except Exception as e:
            logger.error('Control server unreachable or other error. Using local config.')
            logger.error(e)
            if LOCAL_CONFIG['WEB_SERVICE']['DISABLE_FALLBACK']:
                logger.info('Falback disabled. Exiting...')
                sys.exit()
            spec = importlib.util.spec_from_file_location("module.name", cli_args.RULES_FILE)
            rules_module = importlib.util.module_from_spec(spec)
            try:
                spec.loader.exec_module(rules_module)
                logger.info('(ROUTER) Routing bridges file found and bridges imported: %s', cli_args.RULES_FILE)
            except (ImportError, FileNotFoundError):
                sys.exit('(ROUTER) TERMINATING: Routing bridges file not found or invalid: {}'.format(cli_args.RULES_FILE))
            # Build the routing rules file
            BRIDGES = make_bridges(rules_module.BRIDGES, False)
            # Get rule parameter for private calls
            UNIT = gen_proxy_unit(rules_module.UNIT)
            unit_flood_time = rules_module.FLOOD_TIMEOUT

    else:
        spec = importlib.util.spec_from_file_location("module.name", cli_args.RULES_FILE)
        rules_module = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(rules_module)
            logger.info('(ROUTER) Routing bridges file found and bridges imported: %s', cli_args.RULES_FILE)
        except (ImportError, FileNotFoundError):
            sys.exit('(ROUTER) TERMINATING: Routing bridges file not found or invalid: {}'.format(cli_args.RULES_FILE))
            spec = importlib.util.spec_from_file_location("module.name", cli_args.RULES_FILE)
##        print('--------')
##        print(rules_module.BRIDGES)
        # Build the routing rules file
        BRIDGES = make_bridges(rules_module.BRIDGES, False)
        # Get rule parameter for private calls
        UNIT = gen_proxy_unit(rules_module.UNIT)
        unit_flood_time = rules_module.FLOOD_TIMEOUT

    for system in CONFIG['SYSTEMS']:
        if CONFIG['SYSTEMS'][system]['ENABLED']:
            if CONFIG['SYSTEMS'][system]['MODE'] == 'OPENBRIDGE':
                systems[system] = routerOBP(system, CONFIG, report_server)
            else:
                systems[system] = routerHBP(system, CONFIG, report_server)
            reactor.listenUDP(CONFIG['SYSTEMS'][system]['PORT'], systems[system], interface=CONFIG['SYSTEMS'][system]['IP'])
            logger.debug('(GLOBAL) %s instance created: %s, %s', CONFIG['SYSTEMS'][system]['MODE'], system, systems[system])

    def loopingErrHandle(failure):
        logger.error('(GLOBAL) STOPPING REACTOR TO AVOID MEMORY LEAK: Unhandled error in timed loop.\n %s', failure)
        reactor.stop()

    
    # Initialize the rule timer -- this if for user activated stuff
    rule_timer_task = task.LoopingCall(rule_timer_loop, unit_flood_time)
    rule_timer = rule_timer_task.start(60)
    rule_timer.addErrback(loopingErrHandle)

    # Initialize the stream trimmer
    stream_trimmer_task = task.LoopingCall(stream_trimmer_loop)
    stream_trimmer = stream_trimmer_task.start(5)
    stream_trimmer.addErrback(loopingErrHandle)

    # Used for misc timing events
    ten_loop_task = task.LoopingCall(ten_loop_func)
    ten_loop = ten_loop_task.start(600)
    ten_loop.addErrback(loopingErrHandle)

    logger.info('UNIT calls will be bridged to: ' + str(UNIT))
##    print(CONFIG)
##    # Download burn list
##    if LOCAL_CONFIG['WEB_SERVICE']['REMOTE_CONFIG_ENABLED']:
##        with open(CONFIG['WEB_SERVICE']['BURN_FILE'], 'w') as f:
##            f.write(str(download_burnlist(CONFIG)))
    
    # Create folder so hbnet.py can access list PEER connections
    print(CONFIG['LOGGER']['LOG_NAME'])
    if Path('/tmp/' + (CONFIG['LOGGER']['LOG_NAME'] + '_PEERS/')).exists():
        try:
            os.remove('/tmp/' + (CONFIG['LOGGER']['LOG_NAME'] + '_PEERS/*'))
        except Exception as e:
            logger.error(e)
            pass
    else:
        Path('/tmp/' + (CONFIG['LOGGER']['LOG_NAME'] + '_PEERS/')).mkdir()

           
    reactor.run()
