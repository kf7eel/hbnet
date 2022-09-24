#!/usr/bin/env python3
#
###############################################################################
#   HBLink - Copyright (C) 2020 Cortney T. Buffington, N0MJS <n0mjs@me.com>
#   GPS/Data - Copyright (C) 2020 Eric Craw, KF7EEL <kf7eel@qsl.net>
#   Annotated modifications Copyright (C) 2021 Xavier FRS2013
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
This is a data application. It decodes and reassambles DMR GPS packets and
uploads them to APRS-IS. Also does miscelaneous SMS functions.
'''

# Python modules we need
import sys
from bitarray import bitarray
from time import time, strftime, sleep
from importlib import import_module

# Twisted is pretty important, so I keep it separate
from twisted.internet.protocol import Factory, Protocol
from twisted.protocols.basic import NetstringReceiver
from twisted.internet import reactor, task

# Things we import from the main hblink module
from hblink import HBSYSTEM, OPENBRIDGE, systems, hblink_handler, reportFactory, REPORT_OPCODES, mk_aliases, config_reports
from dmr_utils3.utils import bytes_3, int_id, get_alias, bytes_4
from dmr_utils3 import decode, bptc, const
import data_gateway_config
import log
from const import *

# Stuff for socket reporting
import pickle
# REMOVE LATER from datetime import datetime
# The module needs logging, but handlers, etc. are controlled by the parent
import logging
logger = logging.getLogger(__name__)

#### Modules for data gateway ###
# modules from DATA_CONFIG.py
from binascii import b2a_hex as ahex
import re
##from binascii import a2b_hex as bhex
import aprslib
import datetime
from bitarray.util import ba2int as ba2num
from bitarray.util import ba2hex as ba2hx
import codecs
#Needed for working with NMEA
import pynmea2

# Used with HTTP POST
from hashlib import sha256
import json, requests


# Modules for executing commands/scripts
import os
##from gps_functions import cmd_list

# Module for maidenhead grids
try:
    import maidenhead as mh
except:
    logger.error('Error importing maidenhead module, make sure it is installed.')

#Modules for APRS settings
import ast
from pathlib import Path
# Used for APRS
import threading
# Used for SMS encoding
import libscrc
import random
from bitarray.util import hex2ba as hex2bits
import traceback

from socket import gethostbyname

from data_gateway_local_commands import LOCAL_COMMANDS
import subprocess

###################### testing #################3
from scapy.all import IP, UDP, raw
import ipaddress

import paho.mqtt.client as mqtt
import string
import math
#################################

#################################


# Does anybody read this stuff? There's a PEP somewhere that says I should do this.
__author__     = 'Cortney T. Buffington, N0MJS, Eric Craw, KF7EEL, kf7eel@qsl.net'
__copyright__  = 'Copyright (c) 2016-2019 Cortney T. Buffington, N0MJS and the K0USY Group, Copyright (c) 2020-2021, Eric Craw, KF7EEL'
__credits__    = 'Colin Durbridge, G4EML, Steve Zingman, N4IRS; Mike Zingman, N4IRR; Jonathan Naylor, G4KLX; Hans Barthen, DL5DI; Torsten Shultze, DG1HT'
__license__    = 'GNU GPLv3'
__maintainer__ = 'Eric Craw, KF7EEL'
__email__      = 'kf7eel@qsl.net'

sms_seq_num = 0
use_csbk = True
ssid = ''
UNIT_MAP = {}
PACKET_MATCH = {}
mqtt_services = {}
##subscriber_format = {}
btf = {}
sub_hdr = {}
packet_assembly = {}

pistar_overflow = 0.1

peer_aprs = {}

# Keep track of what user needs which SMS format

def sms_type(sub, sms):
    # Port 5016, specified in ETSI 361-3
    # Aparently some radios use UTF-16LE
    subscriber_format = sms_format_retrieve('')
    if sms[40:48] == '13981398' and sms[66:68] == '00':
        subscriber_format[sub] = 'etsi_le'
    # Also, attempt for UTF-16BE
    elif sms[40:48] == '13981398' and sms[64:66] == '00':
        subscriber_format[sub] = 'etsi_be'
    # Port 4007, Motorola
    elif sms[40:48] == '0fa70fa7':
        subscriber_format[sub] = 'motorola'
    else:
        subscriber_format[sub] = 'motorola'
    logger.debug(subscriber_format)

    with open('./subscriber_sms_formats.txt', 'w') as sms_form_file:
        sms_form_file.write(str(subscriber_format))
        sms_form_file.close()
        
def sms_format_man(sub, type_sms):
    subscriber_format = sms_format_retrieve('')
    subscriber_format[to_id] = type_sms
    with open('./subscriber_sms_formats.txt', 'w') as sms_form_file:
        sms_form_file.write(str(subscriber_format))
        sms_form_file.close()

def sms_format_retrieve(sub):
    format_dict = ast.literal_eval(os.popen('cat ./subscriber_sms_formats.txt').read())
    if sub != '':
        return format_dict[sub]
    else:
        return format_dict
    

##mqtt_shortcut_gen = ''.join(random.choices(string.ascii_uppercase, k=4))

def mqtt_main(mqtt_user, mqtt_pass, mqtt_user2, mqtt_pass2, broker_url = 'localhost', broker_port = 1883, broker_url2 = 'localhost', broker_port2 = 1883):
    global mqtt_client, mqtt_client2
    if broker_url2 != '':
        logger.info('Enabling MQTT Server 2')
        mqtt_client2 = mqtt.Client(client_id = mqtt_shortcut_gen + '-' + str(random.randint(1,99)))
    elif broker_url2 == '':
        mqtt_client2 = ''
##    print(broker_port)
    # On connect, send announcement
    def on_connect(client, userdata, flags, rc):
        # Annouyncement happens with ten_loop_func
        logger.debug('Connected to MQTT server: ' + broker_url)
    def on_disconnect(client, userdata, flags, rc):
        logger.debug('Disconnected from MQTT server')
    def mqtt_connect():
        global mqtt_client2
        print('connect')
        # Pass MQTT server details to instrance           
        if mqtt_user != '':
            logger.info('MQTT User/Pass specified')
            mqtt_client.username_pw_set(mqtt_user, mqtt_pass)
        if mqtt_user2 != '':
            logger.info('MQTT User/Pass specified for server 2')
            mqtt_client.username_pw_set(mqtt_user, mqtt_pass)
        mqtt_client.connect(broker_url, broker_port, keepalive = 30)
        if broker_url2 == '':
            mqtt_client2 = ''
            logger.info('Second MQTT server not used')
        elif broker_url2 != '':
            mqtt_client2.connect(broker_url2, broker_port2, keepalive = 30)

    # Process received msg here
    def on_message(client, userdata, message):
        topic_list = str(message.topic).split('/')
##        print(topic_list)
        dict_payload = json.loads(message.payload.decode())
##        print(dict_payload)
        logger.debug(dict_payload)
        if len(topic_list) == 1:
            # Add service/network to dict of known services
            if topic_list[0] == 'ANNOUNCE' and dict_payload[list(dict_payload.keys())[0]] == "LOST_CONNECTION":
                try:
                    logger.debug('Removed MQTT service')
                    del mqtt_services[list(dict_payload.keys())[0]]
                except Exception as e:
                    logger.error('Error with MQTT service removal')
                    logger.error(e)
            elif topic_list[0] == 'ANNOUNCE':
                if '*NO_SMS' in dict_payload['shortcut']:
                    logger.debug('Service discovered, NO_SMS flag, not adding to known services.')
                elif dict_payload['shortcut'] == '':
                    pass
                else:
                    if '*NO_SMS' in mqtt_shortcut_gen:
                        if dict_payload['type'] == 'network':
                            logger.debug('NO_SMS flag, not adding other networks to known services')
                        elif dict_payload['type'] == 'app':
                            logger.info('Service discovered: ' + dict_payload['shortcut'])
                            logger.debug((dict_payload))
                            mqtt_services[dict_payload['shortcut']] = dict_payload
                            logger.debug('Known services: ')
                            logger.debug(mqtt_services)
                    else:
                        logger.info('Service discovered: ' + dict_payload['shortcut'])
                        logger.debug((dict_payload))
                        mqtt_services[dict_payload['shortcut']] = dict_payload
                        logger.debug('Known services: ')
                        logger.debug(mqtt_services) 
        elif len(topic_list) > 1:
            # Incoming MSG
            if topic_list[0] == 'ANNOUNCE' and topic_list[1] == 'MQTT':
##                print(dict_payload)
                send_mb(CONFIG, 'admins', 'MQTT Server', dict_payload['message'], 0, 0, 'MQTT Server')
                logger.debug('Received MQTT server message.........................................................')
            elif topic_list[0] == 'MSG' and list(dict_payload.keys())[1] == 'network' and topic_list[1] == mqtt_shortcut_gen:
                try:
                    if dict_payload['network'] in mqtt_services.keys():
                        if mqtt_services[dict_payload['network']]['type'] == 'network':
                            send_sms(False, int(topic_list[2]), data_id[0], data_id[0], 'unit',  dict_payload['network'] + '/' + list(dict_payload.keys())[0] + ': ' + dict_payload[list(dict_payload.keys())[0]])
                        if mqtt_services[dict_payload['network']]['type'] == 'app':
                            send_sms(False, int(topic_list[2]), data_id[0], data_id[0], 'unit',  dict_payload['network'] + ': ' + dict_payload[list(dict_payload.keys())[0]])
                    else:
                        logger.debug('Received incoming message from network/app that is not discovered yet, dropping.')
                        pass
                except Exception as e:
                    logger.error('Unable to determine if message from network or app, defaulting to network...')
                    logger.error(e)
                    send_sms(False, int(topic_list[2]), data_id[0], data_id[0], 'unit',  dict_payload['network'] + '/' + list(dict_payload.keys())[0] + ': ' + dict_payload[list(dict_payload.keys())[0]])
##            else:
                print(dict_payload)
            
    mqtt_client = mqtt.Client(client_id = mqtt_shortcut_gen + '-' + str(random.randint(1,99)))
    if broker_url2 != '':
        mqtt_client2.will_set("ANNOUNCE", json.dumps({mqtt_shortcut_gen:"LOST_CONNECTION"}), 0, False)
        mqtt_client2.on_message = on_message
        mqtt_client2.on_connect = on_connect
        mqtt_client2.on_disconnect = on_disconnect
    # Last will and testament
    mqtt_client.will_set("ANNOUNCE", json.dumps({mqtt_shortcut_gen:"LOST_CONNECTION"}), 0, False)
    mqtt_client.on_message = on_message
    mqtt_client.on_connect = on_connect
    mqtt_client.on_disconnect = on_disconnect
    mqtt_connect()

    # Subscribe to:
    # Incoming messages
    mqtt_client.subscribe('MSG/' + mqtt_shortcut_gen + '/#', qos=0)
    
    # Announcements for service/network discovery
    mqtt_client.subscribe("ANNOUNCE", qos=0)

    # Announcements from MQTT server operator
    mqtt_client.subscribe("ANNOUNCE/MQTT", qos=0)
    

    if broker_url2 != '':
        mqtt_client2.subscribe('MSG/' + mqtt_shortcut_gen + '/#', qos=0)
        mqtt_client2.subscribe("ANNOUNCE", qos=0)
        mqtt_client2.loop_start()

    mqtt_client.loop_start()
    

def mqtt_send_msg(network_shortcut, rcv_dmr_id, snd_dmr_id, message):
    msg_dict = json.dumps({str(snd_dmr_id):message, 'network':mqtt_shortcut_gen}, indent = 4)
    mqtt_client.publish(topic='MSG/' + network_shortcut + '/' + str(rcv_dmr_id), payload=msg_dict, qos=0, retain=False)
    if mqtt_client2 != '':
        mqtt_client2.publish(topic='MSG/' + network_shortcut + '/' + str(rcv_dmr_id), payload=msg_dict, qos=0, retain=False)
    logger.info('Sent message to another network via MQTT: ' + network_shortcut)
    
def mqtt_send_app(network_shortcut, snd_dmr_id, message):
    msg_dict = json.dumps({'dmr_id': str(snd_dmr_id), 'message':message, 'network':mqtt_shortcut_gen, 'sms_type':'unit'}, indent = 4)
    mqtt_client.publish(topic='APP/' + network_shortcut, payload=msg_dict, qos=0, retain=False)
    if mqtt_client2 != '':
        mqtt_client2.publish(topic='APP/' + network_shortcut, payload=msg_dict, qos=0, retain=False)
    logger.info('Sent message to external application via MQTT: ' + network_shortcut)

def mqtt_announce():
    mqtt_client.publish(topic="ANNOUNCE", payload=json.dumps({'shortcut':mqtt_shortcut_gen, 'type': 'network', 'url':CONFIG['DATA_CONFIG']['URL'], 'description':CONFIG['DATA_CONFIG']['DESCRIPTION']}, indent = 4), qos=0, retain=False)
    if mqtt_client2 != '':
        mqtt_client2.publish(topic="ANNOUNCE", payload=json.dumps({'shortcut':mqtt_shortcut_gen, 'type': 'network', 'url':CONFIG['DATA_CONFIG']['URL'], 'description':CONFIG['DATA_CONFIG']['DESCRIPTION']}, indent = 4), qos=0, retain=False)
  

def download_aprs_settings(_CONFIG):
    user_man_url = _CONFIG['WEB_SERVICE']['URL']
    shared_secret = str(sha256(_CONFIG['WEB_SERVICE']['SHARED_SECRET'].encode()).hexdigest())
    aprs_check = {
    'aprs_settings':True,
    'secret':shared_secret
    }
    json_object = json.dumps(aprs_check, indent = 4)
    try:
        logger.info('Downloading APRS settings')
        set_dict = {}
        req = requests.post(user_man_url, data=json_object, headers={'Content-Type': 'application/json'})
        resp = json.loads(req.text)
        for i in resp['aprs_settings'].items():
            set_dict[int(i[0])] = i[1]
        return set_dict
    # For exception, write blank dict
    except requests.ConnectionError:
        return {}

def ping(CONFIG):
    user_man_url = CONFIG['WEB_SERVICE']['URL']
    shared_secret = str(sha256(CONFIG['WEB_SERVICE']['SHARED_SECRET'].encode()).hexdigest())
    ping_data = {
    'ping': CONFIG['WEB_SERVICE']['THIS_SERVER_NAME'],
    'secret':shared_secret
    }
    json_object = json.dumps(ping_data, indent = 4)
    
    try:
        req = requests.post(user_man_url, data=json_object, headers={'Content-Type': 'application/json'})
        logger.debug('Web service ping')
##        resp = json.loads(req.text)
##        print(resp)
##        return resp['rules']
    except requests.ConnectionError:
        logger.error('Config server unreachable')
##        return config.build_config(cli_file)


def send_dash_loc(CONFIG, call, lat, lon, time, comment, dmr_id):
    user_man_url = CONFIG['WEB_SERVICE']['URL']
    shared_secret = str(sha256(CONFIG['WEB_SERVICE']['SHARED_SECRET'].encode()).hexdigest())
    loc_data = {
    'dashboard': CONFIG['WEB_SERVICE']['THIS_SERVER_NAME'],
    'secret':shared_secret,
    'call': call,
    'lat' : lat,
    'lon' : lon,
    'comment' : comment,
    'dmr_id' : dmr_id
    }
    json_object = json.dumps(loc_data, indent = 4)
    
    try:
        req = requests.post(user_man_url, data=json_object, headers={'Content-Type': 'application/json'})
        logger.info('Position sent to web service')
##        resp = json.loads(req.text)
##        print(resp)
##        return resp['rules']
    except requests.ConnectionError:
        logger.error('Config server unreachable')

def send_sms_log(CONFIG, snd_call, rcv_call, msg, rcv_id, snd_id, system_name):
    user_man_url = CONFIG['WEB_SERVICE']['URL']
    shared_secret = str(sha256(CONFIG['WEB_SERVICE']['SHARED_SECRET'].encode()).hexdigest())
    sms_data = {
    'log_sms': CONFIG['WEB_SERVICE']['THIS_SERVER_NAME'],
    'secret':shared_secret,
    'snd_call': snd_call,
    'rcv_call': rcv_call,
    'message' : msg,
    'snd_id' : snd_id,
    'rcv_id' : rcv_id,
    'system_name': system_name
    }
    json_object = json.dumps(sms_data, indent = 4)
    
    try:
        req = requests.post(user_man_url, data=json_object, headers={'Content-Type': 'application/json'})
        logger.debug('SMS sent to web service')
    except Exception as e:
        logger.error('Exception sending SMS to web service.')
        logger.error(e)

def send_bb(CONFIG, callsign, dmr_id, bulletin, system_name):
    user_man_url = CONFIG['WEB_SERVICE']['URL']
    shared_secret = str(sha256(CONFIG['WEB_SERVICE']['SHARED_SECRET'].encode()).hexdigest())
    sms_data = {
    'bb_send': CONFIG['WEB_SERVICE']['THIS_SERVER_NAME'],
    'secret':shared_secret,
    'callsign': callsign,
    'dmr_id': dmr_id,
    'bulletin': bulletin,
    'system_name' : system_name
    }
    json_object = json.dumps(sms_data, indent = 4)
    
    try:
        req = requests.post(user_man_url, data=json_object, headers={'Content-Type': 'application/json'})
        logger.debug('Posted to BB')
##        resp = json.loads(req.text)
##        print(resp)
##        return resp['rules']
    except requests.ConnectionError:
        logger.error('Config server unreachable')


def send_mb(CONFIG, _dst_callsign, _src_callsign, message, _dst_dmr_id, _src_dmr_id, system_name):
    user_man_url = CONFIG['WEB_SERVICE']['URL']
    shared_secret = str(sha256(CONFIG['WEB_SERVICE']['SHARED_SECRET'].encode()).hexdigest())
    mb_data = {
    'mb_add': CONFIG['WEB_SERVICE']['THIS_SERVER_NAME'],
    'secret':shared_secret,
    'dst_callsign': _dst_callsign,
    'src_callsign': _src_callsign,
    'message' : message,
    'dst_dmr_id' : _dst_dmr_id,
    'src_dmr_id' : _src_dmr_id,
    'system_name' : system_name
    }
    json_object = json.dumps(mb_data, indent = 4)
    
    try:
        req = requests.post(user_man_url, data=json_object, headers={'Content-Type': 'application/json'})
        logger.debug('Posted to mailbox')
##        resp = json.loads(req.text)
##        print(resp)
##        return resp['rules']
    except requests.ConnectionError:
        logger.error('Config server unreachable')

        
def send_ss(CONFIG, callsign, message, dmr_id):
    if LOCAL_CONFIG['WEB_SERVICE']['REMOTE_CONFIG_ENABLED'] == True:
        user_man_url = CONFIG['WEB_SERVICE']['URL']
        shared_secret = str(sha256(CONFIG['WEB_SERVICE']['SHARED_SECRET'].encode()).hexdigest())
        sms_data = {
        'ss_update': CONFIG['WEB_SERVICE']['THIS_SERVER_NAME'],
        'secret':shared_secret,
        'callsign': callsign,
        'message' : message,
        'dmr_id' : dmr_id,

        }
        json_object = json.dumps(sms_data, indent = 4)
        
        try:
            req = requests.post(user_man_url, data=json_object, headers={'Content-Type': 'application/json'})
            logger.debug('Social Status sent.')
    ##        resp = json.loads(req.text)
    ##        print(resp)
    ##        return resp['rules']
        except requests.ConnectionError:
            logger.error('Config server unreachable')

def send_unit_table(CONFIG, _data):
    user_man_url = CONFIG['WEB_SERVICE']['URL']
    shared_secret = str(sha256(CONFIG['WEB_SERVICE']['SHARED_SECRET'].encode()).hexdigest())
    sms_data = {
    'unit_table': CONFIG['WEB_SERVICE']['THIS_SERVER_NAME'],
    'secret':shared_secret,
    'data': str(_data),

    }
    json_object = json.dumps(sms_data, indent = 4)
    
    try:
        req = requests.post(user_man_url, data=json_object, headers={'Content-Type': 'application/json'})
        logger.debug('Sent UNIT table')
##        resp = json.loads(req.text)
##        print(resp)
##        return resp['rules']
    except requests.ConnectionError:
        logger.error('Config server unreachable')

def send_known_services(CONFIG, _data):
    user_man_url = CONFIG['WEB_SERVICE']['URL']
    shared_secret = str(sha256(CONFIG['WEB_SERVICE']['SHARED_SECRET'].encode()).hexdigest())
    sms_data = {
    'known_services': CONFIG['WEB_SERVICE']['THIS_SERVER_NAME'],
    'secret':shared_secret,
    'data': str(_data),

    }
    json_object = json.dumps(sms_data, indent = 4)
    
    try:
        req = requests.post(user_man_url, data=json_object, headers={'Content-Type': 'application/json'})
        logger.debug('Sent MQTT table')
##        resp = json.loads(req.text)
##        print(resp)
##        return resp['rules']
    except requests.ConnectionError:
        logger.error('Config server unreachable')

def send_sms_que_req(CONFIG):
    user_man_url = CONFIG['WEB_SERVICE']['URL']
    shared_secret = str(sha256(CONFIG['WEB_SERVICE']['SHARED_SECRET'].encode()).hexdigest())
    sms_req_data = {
    'get_sms_que': CONFIG['WEB_SERVICE']['THIS_SERVER_NAME'],
    'secret':shared_secret,
    }
    json_object = json.dumps(sms_req_data, indent = 4)
    
    try:
        req = requests.post(user_man_url, data=json_object, headers={'Content-Type': 'application/json'})
        resp = json.loads(req.text)
        logger.debug(resp)
        return resp['que']
    except Exception as e:
        logger.error('Exception with SMS que from web service.')
        logger.error(e)

def send_sms_cmd(CONFIG, _rf_id, _cmd):
    user_man_url = CONFIG['WEB_SERVICE']['URL']
    shared_secret = str(sha256(CONFIG['WEB_SERVICE']['SHARED_SECRET'].encode()).hexdigest())
    sms_cmd_data = {
    'sms_cmd': CONFIG['WEB_SERVICE']['THIS_SERVER_NAME'],
    'secret':shared_secret,
    'rf_id': _rf_id,
    'cmd': _cmd,
    'call': str(get_alias((_rf_id), subscriber_ids))
    }
    json_object = json.dumps(sms_cmd_data, indent = 4)
    
    try:
        req = requests.post(user_man_url, data=json_object, headers={'Content-Type': 'application/json'})
        logger.info('Sent SMS command to web service')
##        resp = json.loads(req.text)
##        print(resp)
##        return resp['que']
    except requests.ConnectionError:
        logger.error('Config server unreachable')


# Function to download config
def download_config(CONFIG_FILE, cli_file):
##    global aprs_callsign
    logger.info('Downloading config from web service...')
    user_man_url = CONFIG_FILE['WEB_SERVICE']['URL']
    shared_secret = str(sha256(CONFIG_FILE['WEB_SERVICE']['SHARED_SECRET'].encode()).hexdigest())
    config_check = {
    'get_config':CONFIG_FILE['WEB_SERVICE']['THIS_SERVER_NAME'],
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
        corrected_config['DATA_CONFIG'] = {}
        iterate_config.update(resp['masters'].copy())
        corrected_config['SYSTEMS'].update(iterate_config)
        corrected_config['LOGGER'].update(CONFIG_FILE['LOGGER'])
##        corrected_config['WEB_SERVICE'].update(resp['config']['WEB_SERVICE'])
        corrected_config['WEB_SERVICE'] = {}
        corrected_config['WEB_SERVICE']['THIS_SERVER_NAME'] = CONFIG_FILE['WEB_SERVICE']['THIS_SERVER_NAME']
        corrected_config['WEB_SERVICE']['URL'] = CONFIG_FILE['WEB_SERVICE']['URL']
        corrected_config['WEB_SERVICE']['DISABLE_FALLBACK'] = CONFIG_FILE['WEB_SERVICE']['DISABLE_FALLBACK']
        corrected_config['WEB_SERVICE']['SHARED_SECRET'] = CONFIG_FILE['WEB_SERVICE']['SHARED_SECRET']
        corrected_config['WEB_SERVICE']['REMOTE_CONFIG_ENABLED'] = CONFIG_FILE['WEB_SERVICE']['REMOTE_CONFIG_ENABLED']
        corrected_config['WEB_SERVICE'].update(resp['config']['WEB_SERVICE'])
        corrected_config['GLOBAL']['TG1_ACL'] = data_gateway_config.acl_build(corrected_config['GLOBAL']['TG1_ACL'], 4294967295)
        corrected_config['GLOBAL']['TG2_ACL'] = data_gateway_config.acl_build(corrected_config['GLOBAL']['TG2_ACL'], 4294967295)
        corrected_config['GLOBAL']['REG_ACL'] = data_gateway_config.acl_build(corrected_config['GLOBAL']['REG_ACL'], 4294967295)
        corrected_config['GLOBAL']['SUB_ACL'] = data_gateway_config.acl_build(corrected_config['GLOBAL']['SUB_ACL'], 4294967295)
##        corrected_config['SYSTEMS'] = {}
        for i in iterate_config:
##            corrected_config['SYSTEMS'][i]['GROUP_HANGTIME'] = int(iterate_config[i]['GROUP_HANGTIME'])
##            corrected_config['SYSTEMS'][i] = {}
##            print(iterate_config[i])
            if iterate_config[i]['MODE'] == 'MASTER' or iterate_config[i]['MODE'] == 'PROXY' or iterate_config[i]['MODE'] == 'OPENBRIDGE':
##                print(iterate_config[i])
                corrected_config['SYSTEMS'][i]['OTHER_OPTIONS'] = iterate_config[i]['OTHER_OPTIONS']
                corrected_config['SYSTEMS'][i]['TG1_ACL'] = data_gateway_config.acl_build(iterate_config[i]['TG1_ACL'], 4294967295)
                corrected_config['SYSTEMS'][i]['TG2_ACL'] = data_gateway_config.acl_build(iterate_config[i]['TG2_ACL'], 4294967295)
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
                corrected_config['SYSTEMS'][i]['OTHER_OPTIONS'] = iterate_config[i]['OTHER_OPTIONS']
                corrected_config['SYSTEMS'][i]['GROUP_HANGTIME'] = int(iterate_config[i]['GROUP_HANGTIME'])
                corrected_config['SYSTEMS'][i]['RADIO_ID'] = int(iterate_config[i]['RADIO_ID']).to_bytes(4, 'big')
                corrected_config['SYSTEMS'][i]['TG1_ACL'] = data_gateway_config.acl_build(iterate_config[i]['TG1_ACL'], 4294967295)
                corrected_config['SYSTEMS'][i]['TG2_ACL'] = data_gateway_config.acl_build(iterate_config[i]['TG2_ACL'], 4294967295)
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
            corrected_config['SYSTEMS'][i]['SUB_ACL'] = data_gateway_config.acl_build(iterate_config[i]['SUB_ACL'], 16776415)
##        print(corrected_config['OTHER']['OTHER_OPTIONS'])

        other_split = corrected_config['OTHER']['OTHER_OPTIONS'].split(';')
        for i in other_split:
            if 'MQTT:' in i:
                mqtt_options = i[5:].split(':')
                for o in mqtt_options:
                    final_options = o.split('=')
                    
                    if final_options[0] == 'gateway_callsign':
                        mqtt_server = corrected_config['DATA_CONFIG']['GATEWAY_CALLSIGN'] = final_options[1].upper()
                    if final_options[0] == 'url':
                        mqtt_port = corrected_config['DATA_CONFIG']['URL'] = final_options[1]
                    if final_options[0] == 'description':
                        mqtt_port = corrected_config['DATA_CONFIG']['DESCRIPTION'] = final_options[1]
                    if final_options[0] == 'server':
                        mqtt_server = corrected_config['DATA_CONFIG']['MQTT_SERVER'] = final_options[1]
                    if final_options[0] == 'port':
                        mqtt_port = corrected_config['DATA_CONFIG']['MQTT_PORT'] = final_options[1]
                    if final_options[0] == 'username':
                        mqtt_port = corrected_config['DATA_CONFIG']['MQTT_USERNAME'] = final_options[1]
                    if final_options[0] == 'password':
                        mqtt_port = corrected_config['DATA_CONFIG']['MQTT_PASSWORD'] = final_options[1]
                    if final_options[0] == 'server2':
                        mqtt_server = corrected_config['DATA_CONFIG']['MQTT_SERVER2'] = final_options[1]
                    if final_options[0] == 'port2':
                        mqtt_port = corrected_config['DATA_CONFIG']['MQTT_PORT2'] = final_options[1]
                    if final_options[0] == 'username2':
                        mqtt_port = corrected_config['DATA_CONFIG']['MQTT_USERNAME2'] = final_options[1]
                    if final_options[0] == 'password2':
                        mqtt_port = corrected_config['DATA_CONFIG']['MQTT_PASSWORD2'] = final_options[1]
            if 'DATA_GATEWAY:' in i:
##                print(i)
                gateway_options = i[13:].split(':')
##                print(gateway_options)
                for o in gateway_options:
##                    print(o)
                    final_options = o.split('=')
##                    print(final_options)
                    if final_options[0] == 'aprs_login_call':
                        corrected_config['DATA_CONFIG']['APRS_LOGIN_CALL'] = final_options[1].upper()
                    if final_options[0] == 'aprs_login_passcode':
                        corrected_config['DATA_CONFIG']['APRS_LOGIN_PASSCODE'] = final_options[1]
                    if final_options[0] == 'aprs_server':
                        corrected_config['DATA_CONFIG']['APRS_SERVER'] = final_options[1]
                    if final_options[0] == 'aprs_filter':
                        corrected_config['DATA_CONFIG']['APRS_FILTER'] = final_options[1]
                    if final_options[0] == 'aprs_port':
                        corrected_config['DATA_CONFIG']['APRS_PORT'] = final_options[1]
                    if final_options[0] == 'default_ssid':
                        corrected_config['DATA_CONFIG']['USER_APRS_SSID'] = final_options[1]
                    if final_options[0] == 'default_comment':
                        corrected_config['DATA_CONFIG']['USER_APRS_COMMENT'] = final_options[1]
                    if final_options[0] == 'data_id':
                        corrected_config['DATA_CONFIG']['DATA_DMR_ID'] = final_options[1]
                    if final_options[0] == 'call_type':
                        corrected_config['DATA_CONFIG']['CALL_TYPE'] = final_options[1]
                    if final_options[0] == 'user_settings':
                        corrected_config['DATA_CONFIG']['USER_SETTINGS_FILE'] = final_options[1]
                    if final_options[0] == 'igate_time':
                        corrected_config['DATA_CONFIG']['IGATE_BEACON_TIME'] = final_options[1]
                    if final_options[0] == 'igate_icon':
                        corrected_config['DATA_CONFIG']['IGATE_BEACON_ICON'] = final_options[1]
                    if final_options[0] == 'igate_comment':
                        corrected_config['DATA_CONFIG']['IGATE_BEACON_COMMENT'] = final_options[1]
                    if final_options[0] == 'igate_lat':
                        corrected_config['DATA_CONFIG']['IGATE_BEACON_LATITUDE'] = final_options[1]
                    if final_options[0] == 'igate_lon':
                        corrected_config['DATA_CONFIG']['IGATE_BEACON_LONGITUDE'] = final_options[1]
                        
                
##        print(corrected_config['SYSTEMS'])
        return corrected_config
    # For exception, write blank dict
    except requests.ConnectionError:
        logger.error('Config server unreachable, defaulting to local config')
        if LOCAL_CONFIG['WEB_SERVICE']['DISABLE_FALLBACK']:
                logger.error('Falback disabled. Exiting...')
                sys.exit()
        return data_gateway_config.build_config(cli_file)

##################################################################################################

# Headers for GPS by model of radio:
# AT-D878 - Unconfirmed Data
# MD-380 - Unified Data Transport


# From dmr_utils3, modified to decode entire packet. Works for 1/2 rate coded data. 
def decode_full(_data):
    binlc = bitarray(endian='big')   
    binlc.extend([_data[136],_data[121],_data[106],_data[91], _data[76], _data[61], _data[46], _data[31]])
    binlc.extend([_data[152],_data[137],_data[122],_data[107],_data[92], _data[77], _data[62], _data[47], _data[32], _data[17], _data[2]  ])
    binlc.extend([_data[123],_data[108],_data[93], _data[78], _data[63], _data[48], _data[33], _data[18], _data[3],  _data[184],_data[169]])
    binlc.extend([_data[94], _data[79], _data[64], _data[49], _data[34], _data[19], _data[4],  _data[185],_data[170],_data[155],_data[140]])
    binlc.extend([_data[65], _data[50], _data[35], _data[20], _data[5],  _data[186],_data[171],_data[156],_data[141],_data[126],_data[111]])
    binlc.extend([_data[36], _data[21], _data[6],  _data[187],_data[172],_data[157],_data[142],_data[127],_data[112],_data[97], _data[82] ])
    binlc.extend([_data[7],  _data[188],_data[173],_data[158],_data[143],_data[128],_data[113],_data[98], _data[83]])
    #This is the rest of the Full LC data -- the RS1293 FEC that we don't need
    # This is extremely important for SMS and GPS though.
    binlc.extend([_data[68],_data[53],_data[174],_data[159],_data[144],_data[129],_data[114],_data[99],_data[84],_data[69],_data[54],_data[39]])
    binlc.extend([_data[24],_data[145],_data[130],_data[115],_data[100],_data[85],_data[70],_data[55],_data[40],_data[25],_data[10],_data[191]])
    return binlc
   

#Convert DMR packet to binary from MMDVM packet and remove Slot Type and EMB Sync stuff to allow for BPTC 196,96 decoding
def bptc_decode(_data):
        binary_packet = bitarray(decode.to_bits(_data[20:]))
        del binary_packet[98:166]
        return decode_full(binary_packet)

def aprs_send(packet):
    if 'N0CALL' in aprs_callsign:
        logger.info('APRS callsign set to N0CALL, packet not sent.')
        pass
    else:
        AIS.sendall(packet)
        logger.info('Packet sent to APRS-IS.')

            

def dashboard_loc_write(call, lat, lon, time, comment, dmr_id):
    if CONFIG['WEB_SERVICE']['REMOTE_CONFIG_ENABLED'] == True:
        send_dash_loc(CONFIG, call, lat, lon, time, comment, dmr_id)
        logger.info('Sent to web service/dashboard')
    else:
        logger.error('Web service/dashboard not enabled.')

    
def dashboard_bb_write(call, dmr_id, time, bulletin, system_name):
    if CONFIG['WEB_SERVICE']['REMOTE_CONFIG_ENABLED'] == True:
        send_bb(CONFIG, call, dmr_id, bulletin, system_name)
        logger.info('Sent to web service/dashboard')
    else:
        logger.info('Web service/dashboard not enabled.')

def dashboard_sms_write(snd_call, rcv_call, rcv_dmr_id, snd_dmr_id, sms, time, system_name):
    if CONFIG['WEB_SERVICE']['REMOTE_CONFIG_ENABLED'] == True:
        send_sms_log(CONFIG, snd_call, rcv_call, sms, rcv_dmr_id, snd_dmr_id, system_name)
        logger.info('Sent to web service/dashboard')
    else:
        logger.errir('Web service/dashboard not enabled.')



def mailbox_write(call, dmr_id, time, message, recipient):
    if CONFIG['WEB_SERVICE']['REMOTE_CONFIG_ENABLED'] == True:
        send_mb(CONFIG, call, recipient, message, 0, 0, 'APRS-IS')

    else:
        logger.error('Web service/dashboard not enabled.')

# Thanks for this forum post for this - https://stackoverflow.com/questions/2579535/convert-dd-decimal-degrees-to-dms-degrees-minutes-seconds-in-python

def decdeg2dms(dd):
   is_positive = dd >= 0
   dd = abs(dd)
   minutes,seconds = divmod(dd*3600,60)
   degrees,minutes = divmod(minutes,60)
   degrees = degrees if is_positive else -degrees

   return (degrees,minutes,seconds)

def user_setting_write(dmr_id, setting, value, call_type):
##    try:
        if CONFIG['WEB_SERVICE']['REMOTE_CONFIG_ENABLED'] == True:
            send_sms_cmd(CONFIG, dmr_id, 'APRS-' + setting + '=' + str(value))
        if CONFIG['WEB_SERVICE']['REMOTE_CONFIG_ENABLED'] == False:
   # Open file and load as dict for modification
            logger.debug(setting.upper())
            with open(user_settings_file, 'r') as f:
    ##            if f.read() == '{}':
    ##                user_dict = {}
                user_dict = ast.literal_eval(f.read())
                logger.debug('Current settings: ' + str(user_dict))
                if dmr_id not in user_dict:
                    user_dict[dmr_id] = [{'call': str(get_alias((dmr_id), subscriber_ids))}, {'ssid': ''}, {'icon': ''}, {'comment': ''}, {'pin': ''}, {'APRS': False}]
                if setting.upper() == 'ICON':
                    user_dict[dmr_id][2]['icon'] = value
                if setting.upper() == 'SSID':
                    user_dict[dmr_id][1]['ssid'] = value  
                if setting.upper() == 'COM':
                    user_comment = user_dict[dmr_id][3]['comment'] = value[0:35]
                if setting.upper() == 'APRS ON':
                    user_dict[dmr_id][5] = {'APRS': True}
                    if call_type == 'unit':
                        send_sms(False, dmr_id, data_id[0], data_id[0], 'unit', 'APRS MSG TX/RX Enabled')
                    if call_type == 'vcsbk':
                        send_sms(False, data_id[0], data_id[0], data_id[0], 'group', 'APRS MSG TX/RX Enabled')
                if setting.upper() == 'APRS OFF':
                    user_dict[dmr_id][5] = {'APRS': False}
                    if call_type == 'unit':
                        send_sms(False, dmr_id, data_id[0], data_id[0], 'unit', 'APRS MSG TX/RX Disabled')
                    if call_type == 'vcsbk':
                        send_sms(False, data_id[0], data_id[0], data_id[0], 'group', 'APRS MSG TX/RX Disabled')
                if setting.upper() == 'PIN':
                    #try:
                        #if user_dict[dmr_id]:
                    user_dict[dmr_id][4]['pin'] = value
                    if call_type == 'unit':
                        send_sms(False, dmr_id, data_id[0], data_id[0], 'unit',  'You can now use your pin on the dashboard.')
                    if call_type == 'vcsbk':
                        send_sms(False, data_id[0], data_id[0], data_id[0], 'group',  'You can now use your pin on the dashboard.')
                        #if not user_dict[dmr_id]:
                        #    user_dict[dmr_id] = [{'call': str(get_alias((dmr_id), subscriber_ids))}, {'ssid': ''}, {'icon': ''}, {'comment': ''}, {'pin': pin}]
                    #except:
                    #    user_dict[dmr_id].append({'pin': value})
                f.close()
                logger.info('Loaded user settings. Write changes.')
        # Write modified dict to file
            with open(user_settings_file, 'w') as user_dict_file:
                user_dict_file.write(str(user_dict))
                user_dict_file.close()
                logger.info('User setting saved')
                f.close()
            
# Process SMS, do something bases on message
def process_sms(_rf_src, sms, call_type, system_name):
    parse_sms = sms.split(' ')
    logger.debug(parse_sms)
##    logger.debug(call_type)
    # Social Status function
    if '*SS' == parse_sms[0]:
        s = ' '
        post = s.join(parse_sms[1:])
        send_ss(CONFIG, str(get_alias(int_id(_rf_src), subscriber_ids)), post, int_id(_rf_src))
    # Offload some commands onto the HBNet web service
    elif '*RSS' in parse_sms[0] or '*RBB' in parse_sms[0] or '*RMB' in parse_sms[0]:
        send_sms_cmd(CONFIG, int_id(_rf_src), sms)
    # Tiny Page query
    elif '?' in parse_sms[0]:
        send_sms_cmd(CONFIG, int_id(_rf_src), sms)
        
    elif parse_sms[0] == 'ECHO':
        send_sms(False, int_id(_rf_src), data_id[0], data_id[0], 'unit', 'ECHO')
    
    elif parse_sms[0] == 'ID':
        logger.info(str(get_alias(int_id(_rf_src), subscriber_ids)) + ' - ' + str(int_id(_rf_src)))
        if call_type == 'unit':
            send_sms(False, int_id(_rf_src), data_id[0], data_id[0], 'unit', 'Your DMR ID: ' + str(int_id(_rf_src)) + ' - ' + str(get_alias(int_id(_rf_src), subscriber_ids)))
##        if call_type == 'vcsbk':
##            send_sms(False, 9, 9, 9, 'group', 'Your DMR ID: ' + str(int_id(_rf_src)) + ' - ' + str(get_alias(int_id(_rf_src), subscriber_ids)))
    elif parse_sms[0] == 'TEST':
        logger.info('It works!')
        if call_type == 'unit':
            send_sms(False, int_id(_rf_src), data_id[0], data_id[0], 'unit',  'It works')
##        if call_type == 'vcsbk':
##            send_sms(False, 9, 9, 9, 'group',  'It works')

    # APRS settings
    elif '*ICON' in parse_sms[0]:
        user_setting_write(int_id(_rf_src), re.sub(' .*|\*','', parse_sms[0]), parse_sms[1], call_type)
    elif '*SSID' in parse_sms[0]:
        user_setting_write(int_id(_rf_src), re.sub(' .*|\*','', parse_sms[0]), parse_sms[1], call_type)
    elif '*COM' in parse_sms[0]:
        user_setting_write(int_id(_rf_src), re.sub(' .*|\*','', parse_sms[0]), parse_sms[1], call_type)
    elif '*PIN' in parse_sms[0]:
        user_setting_write(int_id(_rf_src), re.sub(' .*|\*','', parse_sms[0]), int(parse_sms[1]), call_type)    
    # Write blank entry to cause APRS receive to look for packets for this station.
    elif '*APRS ON' in sms or '*APRS on' in sms:
        user_setting_write(int_id(_rf_src), 'APRS ON', True, call_type)
    elif '*APRS OFF' in sms or '*APRS off' in sms:
        user_setting_write(int_id(_rf_src), 'APRS OFF', False, call_type)
    elif '*BB' in parse_sms[0]:
        dashboard_bb_write(get_alias(int_id(_rf_src), subscriber_ids), int_id(_rf_src), time(), re.sub('\*BB|\*BB ','',sms), system_name)

    # Note to self, rewrite this command
        
##    elif '@' in parse_sms[0][0:1] and 'M-' in parse_sms[1][0:2]:
##        message = re.sub('^@|.* M-|','',sms)
##        recipient = re.sub('@| M-.*','',sms)
##        mailbox_write(get_alias(int_id(_rf_src), subscriber_ids), int_id(_rf_src), time(), message, str(recipient).upper())

        
    elif '*MH' in parse_sms[0]:
        grid_square = parse_sms[1]
        if len(grid_square) < 6:
            send_sms(False, int_id(_rf_src), data_id[0], data_id[0], 'unit',  'Grid square needs to be 6 characters.')
        elif len(grid_square) > 5:
            lat = decdeg2dms(mh.to_location(grid_square)[0])
            lon = decdeg2dms(mh.to_location(grid_square)[1])
           
            if lon[0] < 0:
                lon_dir = 'W'
            if lon[0] > 0:
                lon_dir = 'E'
            if lat[0] < 0:
                lat_dir = 'S'
            if lat[0] > 0:
                lat_dir = 'N'
            #logger.info(lat)
            #logger.info(lat_dir)
            aprs_lat = str(str(re.sub('\..*|-', '', str(lat[0]))).zfill(2) + str(re.sub('\..*', '', str(lat[1])).zfill(2) + '.')) + '  ' + lat_dir
            aprs_lon = str(str(re.sub('\..*|-', '', str(lon[0]))).zfill(3) + str(re.sub('\..*', '', str(lon[1])).zfill(2) + '.')) + '  ' + lon_dir
            logger.debug('Latitude: ' + str(aprs_lat))
            logger.debug('Longitude: ' + str(aprs_lon))
            # 14FRS2013 simplified and moved settings retrieval
            user_settings = ast.literal_eval(os.popen('cat ' + user_settings_file).read())	
            if int_id(_rf_src) not in user_settings:	
                ssid = str(user_ssid)	
                icon_table = '/'	
                icon_icon = '['	
                comment = aprs_comment + ' DMR ID: ' + str(int_id(_rf_src)) 	
            else:	
                if user_settings[int_id(_rf_src)][1]['ssid'] == '':	
                    ssid = user_ssid	
                if user_settings[int_id(_rf_src)][3]['comment'] == '':	
                    comment = aprs_comment + ' DMR ID: ' + str(int_id(_rf_src))	
                if user_settings[int_id(_rf_src)][2]['icon'] == '':	
                    icon_table = '/'	
                    icon_icon = '['	
                if user_settings[int_id(_rf_src)][2]['icon'] != '':	
                    icon_table = user_settings[int_id(_rf_src)][2]['icon'][0]	
                    icon_icon = user_settings[int_id(_rf_src)][2]['icon'][1]	
                if user_settings[int_id(_rf_src)][1]['ssid'] != '':	
                    ssid = user_settings[int_id(_rf_src)][1]['ssid']	
                if user_settings[int_id(_rf_src)][3]['comment'] != '':	
                    comment = user_settings[int_id(_rf_src)][3]['comment']	
            aprs_loc_packet = str(get_alias(int_id(_rf_src), subscriber_ids)) + '-' + ssid + '>APHBL3,TCPIP*:@' + str(datetime.datetime.utcnow().strftime("%H%M%Sh")) + str(aprs_lat) + icon_table + str(aprs_lon) + icon_icon + '/' + str(comment)
            logger.info(aprs_loc_packet)
            logger.debug('User comment: ' + comment)
            logger.debug('User SSID: ' + ssid)
            logger.debug('User icon: ' + icon_table + icon_icon)
            try:
                aprslib.parse(aprs_loc_packet)
                aprs_send(aprs_loc_packet)
                dashboard_loc_write(str(get_alias(int_id(_rf_src), subscriber_ids)) + '-' + ssid, aprs_lat, aprs_lon, time(), comment, int_id(_rf_src))
                logger.info('Sent maidenhed position to APRS')
            except Exception as error_exception:
                logger.error('Exception. Not uploaded')
                logger.error(error_exception)
                logger.error(str(traceback.extract_tb(error_exception.__traceback__)))
##        packet_assembly = ''
          
    elif '.' == parse_sms[0][0:1]:
        logger.debug('Known shortcuts: ' + str(mqtt_services.keys()))
        if parse_sms[0][1:] in mqtt_services.keys():
            mqtt_send_msg(str(parse_sms[0])[1:], parse_sms[1], int_id(_rf_src), ' '.join(parse_sms[2:]))
        else:
##            # Add error message
            pass
    elif '#' == parse_sms[0][0:1]:
        logger.debug('Known shortcuts: ' + str(mqtt_services.keys()))
        if parse_sms[0][1:] in mqtt_services.keys():
            mqtt_send_app(str(parse_sms[0])[1:], str(int_id(_rf_src)), ' '.join(parse_sms[1:]))
        else:
            # Add error message
            pass
        
    elif '@' in parse_sms[0][0:1] and ' ' in sms: #'M-' not in parse_sms[1][0:2] or '@' not in parse_sms[0][1:]:
        #Example SMS text: @ARMDS This is a test.
        s = ' '
        aprs_dest = re.sub('@', '', parse_sms[0])#re.sub('@| A-.*','',sms)
        aprs_msg = s.join(parse_sms[1:])#re.sub('^@|.* A-|','',sms)
        logger.info(aprs_msg)
        logger.info('APRS message to ' + aprs_dest.upper() + '. Message: ' + aprs_msg)
        user_settings = ast.literal_eval(os.popen('cat ' + user_settings_file).read())
        if int_id(_rf_src) in user_settings and user_settings[int_id(_rf_src)][1]['ssid'] != '':
            ssid = user_settings[int_id(_rf_src)][1]['ssid']
        else:
            ssid = user_ssid
        try:
            if user_settings[int_id(_rf_src)][5]['APRS'] == True:
                aprs_msg_pkt = str(get_alias(int_id(_rf_src), subscriber_ids)) + '-' + str(ssid) + '>APHBL3,TCPIP*::' + str(aprs_dest).ljust(9).upper() + ':' + aprs_msg[0:73]
                logger.info('DMR User: ' + str(int_id(_rf_src)) + ' sending APRS message to ' + str(aprs_dest).ljust(9).upper())
                logger.debug(aprs_msg_pkt)
                try:
                    aprslib.parse(aprs_msg_pkt)
                    aprs_send(aprs_msg_pkt)
                except Exception as error_exception:
                    logger.error('Error sending message packet.')
                    logger.error(error_exception)
                    logger.error(str(traceback.extract_tb(error_exception.__traceback__)))
            else:
                if call_type == 'unit':
                    send_sms(False, int_id(_rf_src), data_id[0], data_id[0], 'unit',  'APRS Messaging must be enabled. Send command "@APRS ON" or use dashboard to enable.')
##                if call_type == 'vcsbk':
##                    send_sms(False, 9, 9, 9, 'group',  'APRS Messaging must be enabled. Send command "@APRS ON" or use dashboard to enable.')
                
        except Exception as e:
            if call_type == 'unit':
                    send_sms(False, int_id(_rf_src), data_id[0], data_id[0], 'unit',  'APRS Messaging must be enabled. Send command "@APRS ON" or use dashboard to enable.')
                    logger.error('User APRS messaging disabled.')
##            if call_type == 'vcsbk':
##                send_sms(False, 9, 9, 9, 'group',  'APRS Messaging must be enabled. Send command "@APRS ON" or use dashboard to enable.')
    elif '%' in parse_sms[0]:
        try:
##            if parse_sms[0][1:] in LOCAL_COMMANDS:
        
            logger.info('Executing command/script.')
            subprocess.Popen(LOCAL_COMMANDS[parse_sms[0][1:]], shell=False)
        except Exception as error_exception:
            logger.info('Exception. Command possibly not in list, or other error.')
            logger.info(error_exception)
##        logger.info(str(traceback.extract_tb(error_exception.__traceback__)))
    else:
        pass

##### SMS encode #########
############## SMS Que and functions ###########

def gen_sms_seq():
    global sms_seq_num
    if sms_seq_num < 255:
        sms_seq_num = sms_seq_num + 1
    if sms_seq_num > 255:
        sms_seq_num = 1
##    print(sms_seq_num)
    return str(hex(sms_seq_num))[2:].zfill(2)
    
def create_crc16(fragment_input):
    crc16 = libscrc.gsm16(bytearray.fromhex(fragment_input))
    return fragment_input + re.sub('x', '0', str(hex(crc16 ^ 0xcccc))[-4:])

def create_crc32(fragment_input):
    # Create and append CRC32 to data
    # Create list of hex
    word_list = []
    count_index = 0
    while count_index < len(fragment_input):
        word_list.append((fragment_input[count_index:count_index + 2]))
        count_index = count_index + 2
    # Create string of rearranged word_list to match ETSI 102 361-1 pg 141
    lst_index = 0
    crc_string = ''
    for i in (word_list):
        if lst_index % 2 == 0:
            crc_string =  crc_string + word_list[lst_index + 1]
            #print(crc_string)
        if lst_index % 2 == 1:
            crc_string = crc_string + word_list[lst_index - 1]
            #print(crc_string)
        lst_index = lst_index + 1
    # Create bytearray of word_list_string
   # print(crc_string)
    word_array = libscrc.posix(bytearray.fromhex(crc_string))
    # XOR to get almost final CRC
    pre_crc = str(hex(word_array ^ 0xffffffff))[2:]
    # Rearrange pre_crc for transmission
    crc = ''
    c = 8
    while c > 0:
        crc = crc + pre_crc[c-2:c]
        c = c - 2
    #crc = crc.zfill(8)
    crc = crc.ljust(8, '0')
    # Return original data and append CRC32
    logger.debug('CRC32 Output: ' + fragment_input + crc)
    return fragment_input + crc


def btf_poc(fragment_input):
    # Break fragment into 12 octet chunks
    chunks = []
    count_index = 0
    while count_index < len(fragment_input):
        chunks.append((fragment_input[count_index:count_index + 24]))
        count_index = count_index + 24
    # Current blocks
    blocks = len(chunks)
    # nearest multiple of 12 - below gives POC
    pre_poc = int((len(fragment_input)/2) + 4)
    # Need extra block
    if blocks * 12 < pre_poc:
        tot_blocks = (blocks + 1) * 12
        poc = tot_blocks - pre_poc
        chunks.append('0' * poc)
    # Don't need extra block
    if blocks * 12 > pre_poc:
        poc = ((blocks * 12)- pre_poc)
##        chunks.append('0' * poc)
        chunks[-1] = chunks[-1] + ('0' * poc * 2)
    # Perfect, POC 0, no extra block
    if blocks * 12 == pre_poc:
        poc = 0
    # Zero out last block
    chunks[-1] = chunks[-1].ljust(poc * 2, '0')
    # Get new BTF, make string
    corrected_frag = ''
    for i in chunks:
        corrected_frag = corrected_frag + i

    total_btf = int(len(chunks))

    logger.debug('POC: ' + str(poc))
    logger.debug('BTF: ' + str(total_btf))

    return total_btf, poc, corrected_frag


def create_crc16_csbk(fragment_input):
    crc16_csbk = libscrc.gsm16(bytearray.fromhex(fragment_input))
    return fragment_input + re.sub('x', '0', str(hex(crc16_csbk ^ 0xa5a5))[-4:])

def csbk_gen2(to_id, from_id, tot_block):
    csbk_lst = []
    csbk_pk = 'BD0080'
    csbk_n = 0
    csbk_tot = 1
    while csbk_n < csbk_tot:
        csbk_lst.append(csbk_pk)
        csbk_n = csbk_n + 1

    send_seq_list = ''
    tot_block = tot_block + csbk_tot
    for block in csbk_lst:
        block = block + str(ahex(tot_block.to_bytes(1, 'big')))[2:-1] + to_id + from_id#str(ahex(int(tot_block))[2:-1])
        block  = create_crc16_csbk(block)
        send_seq_list = send_seq_list + block
        tot_block = tot_block - 1

    return send_seq_list

def mmdvm_encapsulate(dst_id, src_id, peer_id, _seq, _slot, _call_type, _dtype_vseq, _stream_id, _dmr_data):
    signature = 'DMRD'
    # needs to be in bytes
    frame_type = 0x10 #bytes_2(int(10))
    if isinstance(dst_id, str) == False:
        dst_id = str(hex(dst_id))[2:].zfill(6)
    if isinstance(src_id, str) == False:
        src_id = str(hex(src_id))[2:].zfill(6)
    if isinstance(peer_id, str) == False:
        peer_id = str(hex(peer_id))[2:].zfill(8)  
    dest_id = bytes_3(int(dst_id, 16))
    #print(ahex(dest_id))
    source_id = bytes_3(int(src_id, 16))
    via_id = bytes_4(int(peer_id, 16))
    #print(ahex(via_id))
    seq = int(_seq).to_bytes(1, 'big')
    #print(ahex(seq))
    # Binary, 0 for 9, 9 for 2
    slot = bitarray(str(_slot))
    #print(slot)
    # binary, 0 for group, 1 for unit, bin(1)
    call_type = bitarray(str(_call_type))
    #print(call_type)
    #0x00 for voice, 0x01 for voice sync, 0x10 for data 
    #frame_type = int(16).to_bytes(1, 'big')
    frame_type = bitarray('10')
    #print(frame_type)
    # Observed to be always 7, int. Will be 6 for header
    #dtype_vseq = hex(int(_dtype_vseq)).encode()
    if _dtype_vseq == 6:
        dtype_vseq = bitarray('0110')
    if _dtype_vseq == 7:
        dtype_vseq = bitarray('0111')
    if _dtype_vseq == 3:
        dtype_vseq = bitarray('0011')
    # 9 digit integer in hex
    stream_id = bytes_4(_stream_id)
    #print(ahex(stream_id))

    middle_guts = slot + call_type + frame_type + dtype_vseq
    #print(middle_guts)
    dmr_data = str(_dmr_data)[2:-1] #str(re.sub("b'|'", '', str(_dmr_data)))
    complete_packet = signature.encode() + seq + source_id + dest_id + via_id + middle_guts.tobytes() + stream_id + bytes.fromhex((dmr_data))# + bitarray('0000000000101111').tobytes()#bytes.fromhex(dmr_data)
    #print('Complete: ' + str(ahex(complete_packet)))
    return complete_packet


# Break long string into block sequence
def block_sequence(input_string):
    seq_blocks = len(input_string)/24
    n = 0
    block_seq = []
##    csbk_n = 0
    csbk_seq = []
    while n < seq_blocks:
        if n == 0:
            if input_string[:6] == 'BD0080':
                csbk_seq.append(bytes.fromhex(input_string[:24].ljust(24,'0')))
##            elif input_string[:6] != 'BD0080':
            else:
                block_seq.append(bytes.fromhex(input_string[:24].ljust(24,'0')))
            n = n + 1
        else:
##            print('blok seq ' + str((input_string[n*24:n*24+24])))
            if str(input_string[n*24:n*24+24])[:6] == 'BD0080':
                csbk_seq.append(bytes.fromhex(input_string[n*24:n*24+24].ljust(24,'0')))
##            elif str(input_string[n*24:n*24+24])[:6] != 'BD0080':
            else:
                block_seq.append(bytes.fromhex(input_string[n*24:n*24+24].ljust(24,'0')))
            n = n + 1
    return block_seq, csbk_seq

# Takes list of DMR packets, 12 bytes, then encodes them
def dmr_encode(packet_list, _slot):
    send_seq = []
    for i in packet_list:
        stitched_pkt = bptc.interleave_19696(bptc.encode_19696(i))
        l_slot = bitarray('0111011100')
        r_slot = bitarray('1101110001')
        #Mobile Station
       # D5D7F77FD757
        sync_data = bitarray('110101011101011111110111011111111101011101010111')
##        if _slot == 0:
##            # TS1 - F7FDD5DDFD55
##            sync_data = bitarray('111101111111110111010101110111011111110101010101')
##        if _slot == 1:
##            #TS2 - D7557F5FF7F5
##            sync_data = bitarray('110101110101010101111111010111111111011111110101')
##            
        # Data sync? 110101011101011111110111011111111101011101010111 - D5D7F77FD757
        new_pkt = ahex(stitched_pkt[:98] + l_slot + sync_data + r_slot + stitched_pkt[98:])
        send_seq.append(new_pkt)
    return send_seq


def create_sms_seq(dst_id, src_id, peer_id, _slot, _call_type, dmr_string):
##    print('mmdvm_enc')
##    print(dmr_string)
    rand_seq = random.randint(1, 999999)
    block_seq = block_sequence(dmr_string)
    dmr_list = dmr_encode(block_seq[0], _slot)
    csbk_list = dmr_encode(block_seq[1], _slot)
    cap_in = 0
    mmdvm_send_seq = []
    csbk_seq = []
    for i in csbk_list:
        the_mmdvm_pkt = mmdvm_encapsulate(dst_id, src_id, peer_id, cap_in, _slot, _call_type, 3, rand_seq, i)
        csbk_seq.append(the_mmdvm_pkt)   
    for i in dmr_list:
        if cap_in == 0:
            the_mmdvm_pkt = mmdvm_encapsulate(dst_id, src_id, peer_id, cap_in, _slot, _call_type, 6, rand_seq, i) #(bytes.fromhex(re.sub("b'|'", '', str(orig_cap[cap_in][20:-4])))))
        else:
            the_mmdvm_pkt = mmdvm_encapsulate(dst_id, src_id, peer_id, cap_in, _slot, _call_type, 7, rand_seq, i)#(bytes.fromhex(re.sub("b'|'", '', str(orig_cap[cap_in][20:-4])))))
        mmdvm_send_seq.append(the_mmdvm_pkt)
        cap_in = cap_in + 1
            
##    if CONFIG['WEB_SERVICE']['REMOTE_CONFIG_ENABLED'] == False:  
##        with open('/tmp/.hblink_data_que_' + str(CONFIG['DATA_CONFIG']['APRS_LOGIN_CALL']).upper() + '/' + str(random.randint(1000, 9999)) + '.mmdvm_seq', "w") as packet_write_file:
##            packet_write_file.write(str(mmdvm_send_seq))
            
    return csbk_seq + mmdvm_send_seq


def format_sms(msg, to_id, from_id, call_type, use_header = True):

    call_seq_num = gen_sms_seq()

    # Convert DMR ID to integer, the IP for Scapy
    # 0c adds 12. to the IP address, refferred as the CAI
    hex_2_ip_src = str('0c' + from_id)
    hex_2_ip_dest = str('0c' + to_id)
    src_dmr_id = str(ipaddress.IPv4Address(int(hex_2_ip_src, 16)))
    dst_dmr_id = str(ipaddress.IPv4Address(int(hex_2_ip_dest, 16)))

    sms_form = sms_format_retrieve('')
    if to_id not in sms_form.keys():
        sms_format_man(to_id, 'motorola')
        
    if 'etsi_' in sms_format_retrieve(to_id): # == 'etsi_le':
        # Anytone "DMR Standard decodes utf-15 LE, not BE. BE is specified in ETSI 361-3
        if sms_format_retrieve(to_id) == 'etsi_le':
            final = str(ahex(msg.encode('utf-16le')))[2:-1]
            logger.debug('Sending in ETSI?(LE) format.')
        if sms_format_retrieve(to_id) == 'etsi_be':
            final = str(ahex(msg.encode('utf-16be')))[2:-1]
            logger.debug('Sending in ETSI?(BE) format.')
        sms_header = '000d000a'
        ip_udp = IP(dst=dst_dmr_id, src=src_dmr_id, ttl=1, id=int(call_seq_num, 16))/UDP(sport=5016, dport=5016)/(bytes.fromhex(sms_header + final) + bytes.fromhex('00'))# + bytes.fromhex('0000000000000000000000'))
        
    elif sms_format_retrieve(to_id) == 'motorola':
        final = str(ahex(msg.encode('utf-16be')))[2:-1]
        # Unknown what byte is for, but it does correlate to the charaters : (number of characters + 4) * 2 . Convert to bytes.
        unk_count = int((len(msg) + 4) * 2).to_bytes(1, 'big')
##        hdr_seq_num = (ahex(int((int(call_seq_num, 16) + 128)).to_bytes(1, 'big')))
        hdr_seq_num = (ahex(int((random.randint(1,7) + 128)).to_bytes(1, 'big')))
        sms_header = '00' + str(ahex(unk_count))[2:-1] + 'a000' + str(hdr_seq_num)[2:-1] + '040d000a'
        ip_udp = IP(dst=dst_dmr_id, src=src_dmr_id, ttl=1, id=int(call_seq_num, 16))/UDP(sport=5016, dport=5016)/(bytes.fromhex(sms_header + final) + bytes.fromhex('00'))# + bytes.fromhex('0000000000000000000000'))
        logger.debug('Sending in Motorola format')
       
    header_bits = btf_poc(str(ahex(raw(ip_udp)))[2:-1])
    sms_complete_header = create_crc16(gen_header2(to_id, from_id, call_type, header_bits[1], header_bits[0]))
    sms_csbk = (csbk_gen2(to_id, from_id, header_bits[0]))
    logger.debug(sms_complete_header)


    # Return corrected fragment with BTF and generate CRC16 with header

    return header_bits[2], sms_complete_header, sms_csbk #str(ahex(raw(ip_udp)))[2:-1]


def gen_header2(to_id, from_id, call_type, poc, btf):
    s_poc = hex(poc)[2:]

    seq_header = ''
    if call_type == 1:
        seq_header = '024' + s_poc + to_id + from_id + ba2hx(bitarray('1' + str(bin(btf))[2:].zfill(7))) + '50'
    if call_type == 0:
        seq_header = '824' + s_poc + to_id + from_id + ba2hx(bitarray('1' + str(bin(btf))[2:].zfill(7))) + '50'

##    print(seq_header)
    return seq_header

def send_sms(csbk, to_id, from_id, peer_id, call_type, msg, snd_slot = 1):
    global use_csbk
    sleep(1)
    use_csbk = csbk
    to_id = str(hex(to_id))[2:].zfill(6)
    from_id = str(hex(from_id))[2:].zfill(6)
    peer_id = str(hex(peer_id))[2:].zfill(8)
    ascii_call_type = call_type
    if call_type == 'unit':
        call_type = 1
        slot = snd_slot
##        # Try to find slot from UNIT_MAP
##        try:
##            #Slot 2
##            if UNIT_MAP[bytes.fromhex(to_id)][2] == 2:
##                slot = 1
##            # Slot 1
##            if UNIT_MAP[bytes.fromhex(to_id)][2] == 1:
##                slot = 0
##        except Exception as e:
##            logger.info(e)
##            # Change to config value later
##            slot = 1
    if call_type == 'group':
        call_type = 0
        # Send all Group data to TS 2, need to fix later.
        slot = snd_slot

    # Split message in to multiple if msg characters > 100. 95 is for message count
    text_list = []
    text_block_count = 0
    sms_count = 1
    tot_blocks = int(math.ceil(len(msg) / 100.0))
    while text_block_count < len(msg):
        if tot_blocks == 1:
            text_list.append((msg[text_block_count:text_block_count + 95]))
            text_block_count = text_block_count + 95
        else:
            text_list.append(str(sms_count) + '/' + str(tot_blocks) + ': ' + (msg[text_block_count:text_block_count + 95]))
            text_block_count = text_block_count + 95
        sms_count = sms_count + 1


    for m in text_list:
        complete_sms = format_sms(str(m), to_id, from_id, call_type)
        csbk_blocks = str(complete_sms[2])
        headers = str(complete_sms[1])
        sms_data = str(create_crc32(complete_sms[0]))

       # Using CSBK for now, will deal with later.
##        if csbk == True:
        snd_sms = csbk_blocks + headers + sms_data
##        elif csbk == False:
##            snd_sms = headers + sms_data

        if ascii_call_type == 'unit':
            # We know where the user is
            if bytes.fromhex(to_id) in UNIT_MAP:
        ##        print(CONFIG['SYSTEMS']) #[UNIT_MAP[bytes.fromhex(to_id)][2]]['MODE'])
                if CONFIG['SYSTEMS'][UNIT_MAP[bytes.fromhex(to_id)][0]]['MODE'] == 'OPENBRIDGE' and CONFIG['SYSTEMS'][UNIT_MAP[bytes.fromhex(to_id)][0]]['BOTH_SLOTS'] == False  and CONFIG['SYSTEMS'][UNIT_MAP[bytes.fromhex(to_id)][0]]['ENABLED'] == True:
                        slot = 0
                        snd_seq_lst = create_sms_seq(to_id, from_id, peer_id, int(slot), call_type, snd_sms)
                        for d in snd_seq_lst:
                            systems[UNIT_MAP[bytes.fromhex(to_id)][0]].send_system(d)
                            # Sleep to prevent overflowing of Pi-Star buffer
                            sleep(pistar_overflow)
                        logger.info('User in map. Sending on TS: ' + str(slot + 1))
                elif CONFIG['SYSTEMS'][UNIT_MAP[bytes.fromhex(to_id)][0]]['MODE'] == 'OPENBRIDGE' and CONFIG['SYSTEMS'][UNIT_MAP[bytes.fromhex(to_id)][0]]['BOTH_SLOTS'] == True or CONFIG['SYSTEMS'][UNIT_MAP[bytes.fromhex(to_id)][0]]['MODE'] != 'OPENBRIDGE' and CONFIG['SYSTEMS'][UNIT_MAP[bytes.fromhex(to_id)][0]]['ENABLED'] == True:
                        snd_seq_lst = create_sms_seq(to_id, from_id, peer_id, int(slot), call_type, snd_sms)
                        for d in snd_seq_lst:
                            systems[UNIT_MAP[bytes.fromhex(to_id)][0]].send_system(d)
                            # Sleep to prevent overflowing of Pi-Star buffer
                            sleep(pistar_overflow)
                        logger.info('User in map. Sending on TS: ' + str(slot + 1))
          # We don't know where the user is
            elif bytes.fromhex(to_id) not in UNIT_MAP:
                for s in CONFIG['SYSTEMS']:
                    if CONFIG['SYSTEMS'][s]['MODE'] == 'OPENBRIDGE' and CONFIG['SYSTEMS'][s]['BOTH_SLOTS'] == False and CONFIG['SYSTEMS'][s]['ENABLED'] == True:
                        slot = 0
                        snd_seq_lst = create_sms_seq(to_id, from_id, peer_id, int(slot), call_type, snd_sms)
                        for d in snd_seq_lst:
                            systems[s].send_system(d)
                          # Sleep to prevent overflowing of Pi-Star buffer
                            sleep(pistar_overflow)
                        logger.info('User not in map. Sending on TS: ' + str(slot + 1))
                    elif CONFIG['SYSTEMS'][s]['MODE'] == 'OPENBRIDGE' and CONFIG['SYSTEMS'][s]['BOTH_SLOTS'] == True and CONFIG['SYSTEMS'][s]['ENABLED'] == True or CONFIG['SYSTEMS'][s]['MODE'] != 'OPENBRIDGE' and CONFIG['SYSTEMS'][s]['ENABLED'] == True:
                        snd_seq_lst = create_sms_seq(to_id, from_id, peer_id, int(slot), call_type, snd_sms)
                        for d in snd_seq_lst:
                            systems[s].send_system(d)
                            # Sleep to prevent overflowing of Pi-Star buffer
                            sleep(pistar_overflow)
                        logger.info('User not in map. Sending on TS: ' + str(slot + 1))
        if ascii_call_type == 'group':
            snd_seq_lst = create_sms_seq(to_id, from_id, peer_id, int(slot), 0, snd_sms)
            for s in CONFIG['SYSTEMS']:
                for d in snd_seq_lst:
                    systems[s].send_system(d)
                    # Sleep to prevent overflowing of Pi-Star buffer
                    sleep(pistar_overflow)


##    if ascii_call_type == 'unit':
##      # We know where the user is
##        if bytes.fromhex(to_id) in UNIT_MAP:
##            logger.debug('UNIT call. Found user in UNIT map')
##    ##        print(CONFIG['SYSTEMS']) #[UNIT_MAP[bytes.fromhex(to_id)][2]]['MODE'])
##            if CONFIG['SYSTEMS'][UNIT_MAP[bytes.fromhex(to_id)][0]]['MODE'] == 'OPENBRIDGE' and CONFIG['SYSTEMS'][UNIT_MAP[bytes.fromhex(to_id)][0]]['BOTH_SLOTS'] == False  and CONFIG['SYSTEMS'][UNIT_MAP[bytes.fromhex(to_id)][0]]['ENABLED'] == True:
##                    slot = 0
##                    snd_seq_lst = create_sms_seq(to_id, from_id, peer_id, int(slot), call_type, create_crc16(gen_header(to_id, from_id, call_type)) + create_crc32(format_sms(str(msg), to_id, from_id)))
##                    logger.info('OBP ' + s + ', BOTH_SLOTS = False. Sending on TS: ' + str(slot + 1))
##                    for d in snd_seq_lst:
##                        systems[UNIT_MAP[bytes.fromhex(to_id)][0]].send_system(d)
##                    
##            elif CONFIG['SYSTEMS'][UNIT_MAP[bytes.fromhex(to_id)][0]]['MODE'] == 'OPENBRIDGE' and CONFIG['SYSTEMS'][UNIT_MAP[bytes.fromhex(to_id)][0]]['BOTH_SLOTS'] == True or CONFIG['SYSTEMS'][UNIT_MAP[bytes.fromhex(to_id)][0]]['MODE'] != 'OPENBRIDGE' and CONFIG['SYSTEMS'][UNIT_MAP[bytes.fromhex(to_id)][0]]['ENABLED'] == True:
##    ##        else:
##                    logger.debug('User in UNIT map, using send function')
##                    snd_seq_lst = create_sms_seq(to_id, from_id, peer_id, int(slot), call_type, create_crc16(gen_header(to_id, from_id, call_type)) + create_crc32(format_sms(str(msg), to_id, from_id)))
##                    send_to_user(to_id, snd_seq_lst, slot, call_type)
##      # We don't know where the user is
##        elif bytes.fromhex(to_id) not in UNIT_MAP:
##            logger.debug('User not in UNIT map. Flooding SYSTEMS')
##            for s in CONFIG['SYSTEMS']:
##                if CONFIG['SYSTEMS'][s]['MODE'] == 'OPENBRIDGE' and CONFIG['SYSTEMS'][s]['BOTH_SLOTS'] == False and CONFIG['SYSTEMS'][s]['ENABLED'] == True:
##                    slot = 0
##                    snd_seq_lst = create_sms_seq(to_id, from_id, peer_id, int(slot), call_type, create_crc16(gen_header(to_id, from_id, call_type)) + create_crc32(format_sms(str(msg), to_id, from_id)))
##                    logger.debug('OBP ' + s + ', BOTH_SLOTS = False. Sending on TS: ' + str(slot + 1))
##                    for d in snd_seq_lst:
##                        systems[s].send_system(d)
##                elif CONFIG['SYSTEMS'][s]['MODE'] == 'OPENBRIDGE' and CONFIG['SYSTEMS'][s]['BOTH_SLOTS'] == True and CONFIG['SYSTEMS'][s]['ENABLED'] == True or CONFIG['SYSTEMS'][s]['MODE'] != 'OPENBRIDGE' and CONFIG['SYSTEMS'][s]['ENABLED'] == True:
##    ##            else:
##                    snd_seq_lst = create_sms_seq(to_id, from_id, peer_id, int(slot), call_type, create_crc16(gen_header(to_id, from_id, call_type)) + create_crc32(format_sms(str(msg), to_id, from_id)))
##                    send_to_user(to_id, snd_seq_lst, slot, call_type)
##                    logger.debug('Using send function.')
##            
##    if ascii_call_type == 'group':
##        logger.debug('Sending group call')
##        snd_seq_lst = create_sms_seq(to_id, from_id, peer_id, int(slot), call_type, create_crc16(gen_header(to_id, from_id, call_type)) + create_crc32(format_sms(str(msg), to_id, from_id)))
##        send_to_user(to_id, snd_seq_lst, slot, ascii_call_type)


##    if bytes.fromhex(to_id) in UNIT_MAP:
##        logger.debug('User in UNIT map.')
##        if CONFIG['SYSTEMS'][UNIT_MAP[bytes.fromhex(to_id)][0]]['MODE'] == 'OPENBRIDGE' and CONFIG['SYSTEMS'][UNIT_MAP[bytes.fromhex(to_id)][0]]['BOTH_SLOTS'] == False  and CONFIG['SYSTEMS'][UNIT_MAP[bytes.fromhex(to_id)][0]]['ENABLED'] == True:
##            slot = 0
##        else:
##            slot = slot
##        snd_seq_lst = create_sms_seq(to_id, from_id, peer_id, int(slot), call_type, create_crc16(gen_header(to_id, from_id, call_type)) + create_crc32(format_sms(str(msg), to_id, from_id)))
##        send_to_user(to_id, snd_seq_lst, int(slot), call_type = 'unit')
##
##    elif bytes.fromhex(to_id) not in UNIT_MAP:
##        sms_snt = False
##        for s in CONFIG['SYSTEMS']:
##            # Found OBP BOTH_SLOTS = False, format for TS 1 and send. Only need this once if multiple OBP since we don't know where ther user is.
##            if CONFIG['SYSTEMS'][s]['MODE'] == 'OPENBRIDGE' and CONFIG['SYSTEMS'][s]['BOTH_SLOTS'] == False and CONFIG['SYSTEMS'][s]['ENABLED'] == True and sms_snt == False:
##                slot = 0
##                snd_seq_lst = create_sms_seq(to_id, from_id, peer_id, int(slot), call_type, create_crc16(gen_header(to_id, from_id, call_type)) + create_crc32(format_sms(str(msg), to_id, from_id)))
##                send_to_user(to_id, snd_seq_lst, int(slot), call_type = 'unit')
##                print(slot)
##                sms_snt = True
##            else:
##                slot = slot
##        snd_seq_lst = create_sms_seq(to_id, from_id, peer_id, int(slot), call_type, create_crc16(gen_header(to_id, from_id, call_type)) + create_crc32(format_sms(str(msg), to_id, from_id)))
##        send_to_user(to_id, snd_seq_lst, int(slot), call_type = 'unit')


# Experimental ARS functions
def ars_resp(msg, to_id, from_id, call_type, use_header = True):
##    msg_bytes = str.encode(msg)
##    encoded = "".join([str('00' + x) for x in re.findall('..',bytes.hex(msg_bytes))] )
##    final = encoded

    call_seq_num = gen_sms_seq()

    # Convert DMR ID to integer, the IP for Scapy
    # 0c adds 12. to the IP address, refferred as the CAI
    hex_2_ip_src = str('0d' + from_id)
    hex_2_ip_dest = str('0c' + to_id)
    src_dmr_id = str(ipaddress.IPv4Address(int(hex_2_ip_src, 16)))
    dst_dmr_id = str(ipaddress.IPv4Address(int(hex_2_ip_dest, 16)))

 
##    # Unknown what byte is for, but it does correlate to the charaters : (number of characters + 4) * 2 . Convert to bytes.
##    unk_count = int((len(msg) + 4) * 2).to_bytes(1, 'big')

    hdr_seq_num = (ahex(int(((random.randint(1,7) + 128)).to_bytes(1, 'big'))))

##    sms_header = '00' + str(ahex(unk_count))[2:-1] + 'a000' + str(hdr_seq_num)[2:-1] + '040d000a'

   
##    ip_udp = packet = IP(dst=dst_dmr_id, src=src_dmr_id)/UDP(sport=4007, dport=4007)/(bytes.fromhex('0012A00083040D000A') + msg.encode('utf-16') + bytes.fromhex('0000000000000000000000'))

    ip_udp = IP(dst=dst_dmr_id, src=src_dmr_id, id=int(call_seq_num, 16), tos = 1)/UDP(sport=4005, dport=4005)/bytes.fromhex(msg)# + bytes.fromhex('0000000000000000000000'))

    header_bits = btf_poc(str(ahex(raw(ip_udp)))[2:-1])


    sms_complete_header = create_crc16(gen_header2(to_id, from_id, call_type, header_bits[1], header_bits[0]))
    sms_csbk = (csbk_gen2(to_id, from_id, header_bits[0]))

##    csbk_blocks = str(complete_sms[2])
    
##    logger.debug(sms_complete_header)


    # Return corrected fragment with BTF and generate CRC16 with header

    return create_crc32(header_bits[2]), sms_complete_header, sms_csbk #str(ahex(raw(ip_udp)))[2:-1]



                
# Take fully formatted list of sequenced MMDVM packets and send
def send_to_user(to_id, seq_lst, slot, call_type = 'unit'):
    if call_type == 'unit':
        # We know where the user is
        if bytes.fromhex(to_id) in UNIT_MAP:
            logger.debug('User in UNIT map.')
            for d in seq_lst:
                systems[UNIT_MAP[bytes.fromhex(to_id)][0]].send_system(d)
            logger.debug('Sent to ' + UNIT_MAP[bytes.fromhex(to_id)][0])

      # We don't know where the user is
        elif bytes.fromhex(to_id) not in UNIT_MAP:
            for s in CONFIG['SYSTEMS']:
                if CONFIG['SYSTEMS'][s]['ENABLED'] == True:
                    for d in seq_lst:
                        systems[s].send_system(d)
                    logger.debug('User not in UNIT map. Sending to all SYSTEMS.')
                    
    elif call_type == 'group':
        logger.debug('Group data')
        for s in CONFIG['SYSTEMS']:
                if CONFIG['SYSTEMS'][s]['ENABLED'] == True:
                    for d in seq_lst:
                        systems[s].send_system(d)
        logger.debug('Group data, sending to all systems.')


def aprs_process(packet):
##    logger.debug(aprslib.parse(packet))
    try:
        if 'addresse' in aprslib.parse(packet):
##            logger.debug('Message packet detected')
##            logger.debug(aprslib.parse(packet))
            recipient = re.sub('-.*','', aprslib.parse(packet)['addresse'])
            recipient_ssid = re.sub('.*-','', aprslib.parse(packet)['addresse']) 
            if recipient == '':
                pass
            else:
                user_settings = ast.literal_eval(os.popen('cat ' + user_settings_file).read())
##                logger.debug('Open user settings to see if this message is for us...')
                for i in user_settings.items():
                    sms_id = i[0]
                    ssid = i[1][1]['ssid']
                    if i[1][1]['ssid'] == '':
                        ssid = user_ssid
                    if recipient in i[1][0]['call'] and i[1][5]['APRS'] == True and recipient_ssid in ssid:
                        logger.debug('Received APRS message from ' + aprslib.parse(packet)['from'] + '. Going to ' + i[1][0]['call'])
                        logger.info('Received APRS message to ' + i[1][0]['call'] + ', sending via SMS and writing to inbox.')
                        mailbox_write(re.sub('-.*','', aprslib.parse(packet)['addresse']), aprslib.parse(packet)['from'], time(), 'From APRS-IS: ' + aprslib.parse(packet)['message_text'], aprslib.parse(packet)['from'])
                        send_sms(False, sms_id, data_id[0], data_id[0], 'unit', str('APRS / ' + str(aprslib.parse(packet)['from']) + ': ' + aprslib.parse(packet)['message_text']))
                        try:
                            if 'msgNo' in aprslib.parse(packet):
                                logger.debug('Message has a message number, sending ACK...')
                                # Write function to check UNIT_MAP and see if X amount of time has passed, if time passed, no ACK. This will prevent multiple gateways from
                                # ACKing. time of 24hrs?
                                if bytes_3(sms_id) in UNIT_MAP:
                                    logger.info(str(aprslib.parse(packet)['addresse']) + '>APHBL3,TCPIP*:' + ':' + str(aprslib.parse(packet)['from'].ljust(9)) +':ack' + str(aprslib.parse(packet)['msgNo']))
                                    aprs_send(str(aprslib.parse(packet)['addresse']) + '>APHBL3,TCPIP*:' + ':' + str(aprslib.parse(packet)['from'].ljust(9)) +':ack' + str(aprslib.parse(packet)['msgNo']))
                                    logger.debug('Sent ACK')
                                else:
                                    logger.debug('Station not seen in 24 hours, no ACK.')
                        except Exception as e:
                            logger.debug('Exception with ACK.')
                            logger.info(e)
    except Exception as e:
        logger.error('Exception while processing APRS packet...')
        logger.error(e)

# the APRS RX process
def aprs_rx(aprs_rx_login, aprs_passcode, aprs_server, aprs_port, aprs_filter, user_ssid):
    global AIS
    AIS = aprslib.IS(aprs_rx_login, passwd=int(aprs_passcode), host=aprs_server, port=int(aprs_port))
    user_settings = ast.literal_eval(os.popen('cat ' + user_settings_file).read())
    AIS.set_filter(aprs_filter)#parser.get('DATA_CONFIG', 'APRS_FILTER'))
    try:
        if 'N0CALL' in aprs_callsign:
            logger.info()
            logger.info('APRS callsign set to N0CALL, not connecting to APRS-IS')
            logger.info()
            pass
        else:
            AIS.connect()
            logger.info('Connecting to APRS-IS')
            if int(CONFIG['DATA_CONFIG']['IGATE_BEACON_TIME']) == 0:
                   logger.info('APRS beacon disabled')
            if int(CONFIG['DATA_CONFIG']['IGATE_BEACON_TIME']) != 0:
                aprs_beacon=task.LoopingCall(aprs_beacon_send)
                aprs_beacon.start(int(CONFIG['DATA_CONFIG']['IGATE_BEACON_TIME'])*60)
            AIS.consumer(aprs_process, raw=True, immortal=False)
    except Exception as e:
        logger.error('Exception, attempting to connect to server...')
        logger.error(e)
        AIS.connect()

        
def aprs_beacon_send():
    logger.debug('Sending iGate APRS beacon...')
    beacon_packet = CONFIG['DATA_CONFIG']['APRS_LOGIN_CALL'] + '>APHBL3,TCPIP*:!' + CONFIG['DATA_CONFIG']['IGATE_BEACON_LATITUDE'] + str(CONFIG['DATA_CONFIG']['IGATE_BEACON_ICON'][0]) + CONFIG['DATA_CONFIG']['IGATE_BEACON_LONGITUDE'] + str(CONFIG['DATA_CONFIG']['IGATE_BEACON_ICON'][1]) + '/' + CONFIG['DATA_CONFIG']['IGATE_BEACON_COMMENT']
    aprslib.parse(beacon_packet)
    aprs_send(beacon_packet)
    logger.debug(beacon_packet)
    peer_aprs_packets()
    logger.info('Uploaded PEER APRS positions')

##### DMR data function ####
def data_received(self, _peer_id, _rf_src, _dst_id, _seq, _slot, _call_type, _frame_type, _dtype_vseq, _stream_id, _data, mirror = False):
    # Capture data headers
##    global hdr_type
    #logger.info(_dtype_vseq)
    #logger.info(_call_type)
    #logger.info(_frame_type)
##    print(int_id(_stream_id))
##    print((_seq))
    logger.info(strftime('%H:%M:%S - %m/%d/%y'))
    logger.debug('Decoded data:')
    logger.debug(ahex(bptc_decode(_data)))
##    logger.info(_seq)
    #logger.info((ba2num(bptc_decode(_data)[8:12])))
################################################################3###### CHNGED #########
##    if int_id(_dst_id) == data_id:
    #logger.info(type(_seq))
    if type(_seq) is bytes:
        pckt_seq = int.from_bytes(_seq, 'big')
    else:
        pckt_seq = _seq
    # Try to classify header
    # UDT header has DPF of 0101, which is 5.
    # If 5 is at position 3, then this should be a UDT header for MD-380 type radios.
    # Coordinates are usually in the very next block after the header, we will discard the rest.
    #logger.info(ahex(bptc_decode(_data)[0:10]))
    if _call_type == call_type and header_ID(_data)[3] == '5' and ba2num(bptc_decode(_data)[69:72]) == 0 and ba2num(bptc_decode(_data)[8:12]) == 0 or (_call_type == 'vcsbk' and header_ID(_data)[3] == '5' and ba2num(bptc_decode(_data)[69:72]) == 0 and ba2num(bptc_decode(_data)[8:12]) == 0):
        global udt_block
        logger.info('MD-380 type UDT header detected. Very next packet should be location.')
        sub_hdr[_rf_src] = '380'
    if _dtype_vseq == 6 and sub_hdr[_rf_src] == '380' or _dtype_vseq == 'group' and sub_hdr[_rf_src] == '380':
        udt_block = 1
    if _dtype_vseq == 7 and sub_hdr[_rf_src] == '380':
        udt_block = udt_block - 1
        if udt_block == 0:
            logger.info('MD-380 type packet. This should contain the GPS location.')
            logger.info('Packet: ' + str(ahex(bptc_decode(_data))))
            if ba2num(bptc_decode(_data)[1:2]) == 1:
                lat_dir = 'N'
            if ba2num(bptc_decode(_data)[1:2]) == 0:
                lat_dir = 'S'
            if ba2num(bptc_decode(_data)[2:3]) == 1:
                lon_dir = 'E'
            if ba2num(bptc_decode(_data)[2:3]) == 0:
                lon_dir = 'W'
            lat_deg = ba2num(bptc_decode(_data)[11:18])
            lon_deg = ba2num(bptc_decode(_data)[38:46])
            lat_min = ba2num(bptc_decode(_data)[18:24])
            lon_min = ba2num(bptc_decode(_data)[46:52])
            lat_min_dec = str(ba2num(bptc_decode(_data)[24:38])).zfill(4)
            lon_min_dec = str(ba2num(bptc_decode(_data)[52:66])).zfill(4)
            # Fix for MD-380 by G7HIF
            aprs_lat = str(str(lat_deg) + str(lat_min).zfill(2) + '.' + str(lat_min_dec)[0:2]).zfill(7) + lat_dir
            aprs_lon = str(str(lon_deg) + str(lon_min).zfill(2) + '.' + str(lon_min_dec)[0:2]).zfill(8) + lon_dir

            # Form APRS packet
            #logger.info(aprs_loc_packet)
            logger.info('Lat: ' + str(aprs_lat) + ' Lon: ' + str(aprs_lon))
            if mirror == False:
            # 14FRS2013 simplified and moved settings retrieval
                user_settings = ast.literal_eval(os.popen('cat ' + user_settings_file).read())
                if int_id(_rf_src) not in user_settings:	
                    ssid = str(user_ssid)	
                    icon_table = '/'	
                    icon_icon = '['	
                    comment = aprs_comment + ' DMR ID: ' + str(int_id(_rf_src)) 	
                else:	
                    if user_settings[int_id(_rf_src)][1]['ssid'] == '':	
                        ssid = user_ssid	
                    if user_settings[int_id(_rf_src)][3]['comment'] == '':	
                        comment = aprs_comment + ' DMR ID: ' + str(int_id(_rf_src))	
                    if user_settings[int_id(_rf_src)][2]['icon'] == '':	
                        icon_table = '/'	
                        icon_icon = '['	
                    if user_settings[int_id(_rf_src)][2]['icon'] != '':	
                        icon_table = user_settings[int_id(_rf_src)][2]['icon'][0]	
                        icon_icon = user_settings[int_id(_rf_src)][2]['icon'][1]	
                    if user_settings[int_id(_rf_src)][1]['ssid'] != '':	
                        ssid = user_settings[int_id(_rf_src)][1]['ssid']	
                    if user_settings[int_id(_rf_src)][3]['comment'] != '':	
                        comment = user_settings[int_id(_rf_src)][3]['comment']
                aprs_loc_packet = str(get_alias(int_id(_rf_src), subscriber_ids)) + '-' + ssid + '>APHBL3,TCPIP*:@' + str(datetime.datetime.utcnow().strftime("%H%M%Sh")) + str(aprs_lat) + icon_table + str(aprs_lon) + icon_icon + '/' + str(comment)
                logger.debug(aprs_loc_packet)
                logger.debug('User comment: ' + comment)
                logger.debug('User SSID: ' + ssid)
                logger.debug('User icon: ' + icon_table + icon_icon)
                logger.info('APRS position generated from MD-380 type radiuo')
                # Attempt to prevent malformed packets from being uploaded.
                try:
                    aprslib.parse(aprs_loc_packet)
                    float(lat_deg) < 91
                    float(lon_deg) < 121
    ##                if int_id(_dst_id) == data_id:
                    if int_id(_dst_id) in data_id:
                        aprs_send(aprs_loc_packet)
                        dashboard_loc_write(str(get_alias(int_id(_rf_src), subscriber_ids)) + '-' + ssid, aprs_lat, aprs_lon, time(), comment, int_id(_rf_src))
                    #logger.info('Sent APRS packet')
                except Exception as error_exception:
                    logger.error('Error. Failed to send packet. Packet may be malformed.')
                    logger.error(error_exception)
                    logger.error(str(traceback.extract_tb(error_exception.__traceback__)))
                udt_block = 1
                sub_hdr[_rf_src] = ''
        else:
              pass
    #NMEA type packets for Anytone like radios.
    # 14FRS2013 contributed improved header filtering, KF7EEL added conditions to allow both call types at the same time
    if _call_type == call_type or (_call_type == 'vcsbk' and pckt_seq > 3 and call_type != 'unit') or (_call_type == 'group' and pckt_seq > 3 and call_type != 'unit') or (_call_type == 'group' and pckt_seq > 3 and call_type == 'both') or (_call_type == 'vcsbk' and pckt_seq > 3 and call_type == 'both') or (_call_type == 'unit' and pckt_seq > 3 and call_type == 'both'): #int.from_bytes(_seq, 'big') > 3 ):
##        global btf
        if _dtype_vseq == 6 or _dtype_vseq == 'group':
##            global hdr_start
            # Header is a "Defined Short Data", used by Hytera I suspect
            if ahex(bptc_decode(_data)[4:-88]) == b'd0':
                logger.debug('Defined Short Data header detected.')
                # Construct blocks to follow
                btf[_rf_src] = (ba2num(bptc_decode(_data)[2:-92] + bptc_decode(_data)[12:-80]))
                sub_hdr[_rf_src] = 'dsd'
            # Everyone else
            else:
                logger.debug('Unconfirmed Data header detected.')
##                hdr_start = str(header_ID(_data))
                logger.info('Header from ' + str(get_alias(int_id(_rf_src), subscriber_ids)) + '. DMR ID: ' + str(int_id(_rf_src)))
                logger.debug(ahex(bptc_decode(_data)))
                logger.info('Blocks to follow: ' + str(ba2num(bptc_decode(_data)[65:72])))
                btf[_rf_src] = ba2num(bptc_decode(_data)[65:72])
                sub_hdr[_rf_src] = ''

        # Data blocks at 1/2 rate, see https://github.com/g4klx/MMDVM/blob/master/DMRDefines.h for data types. _dtype_seq defined here also
        if _dtype_vseq == 7:
            btf[_rf_src] = btf[_rf_src] - 1
            logger.info('Block #: ' + str(btf[_rf_src]))
            #logger.info(_seq)
            logger.info('Data block from ' + str(get_alias(int_id(_rf_src), subscriber_ids)) + '. DMR ID: ' + str(int_id(_rf_src)) + '. Destination: ' + str(int_id(_dst_id)))             
            if _rf_src not in packet_assembly.keys():
                packet_assembly[_rf_src] = ''
            packet_assembly[_rf_src] = packet_assembly[_rf_src] + str(ahex(bptc_decode(_data)))[2:-1] #str((decode_full_lc(b_packet)).strip('bitarray(')))
            # Use block 0 as trigger. $GPRMC must also be in string to indicate NMEA.
            # This triggers the APRS upload or SMS decode
            if btf[_rf_src] == 0:
                sms_hex_string = packet_assembly[_rf_src]
                # Determin SMS format
                sms_type(str(ahex(_rf_src))[2:-1], sms_hex_string)
                sms = codecs.decode(bytes.fromhex(''.join(sms_hex_string[:-8].split('00'))), 'utf-8', 'ignore')
                if sub_hdr[_rf_src] == 'dsd':
                    logger.debug('Trimmed for Defined Short Data')
                    sms_hex_string = sms_hex_string[2:]
                # Filter out ARS
                # Look for port 4005 twice, and 'hello' - 000cf0, and UDP header in first 16 characters
##                if sms_hex_string[40:48] == '0fa50fa5':
                logger.debug('Hexadecimal data: ' + sms_hex_string)
                if '0fa50fa5' in sms_hex_string and '4011' in sms_hex_string[:20]:
                    logger.info('Motorola ARS packet detected')
                    logger.info('Protocol support in progress')
                    if '000cf0' in sms_hex_string:
                        logger.info('Received ARS "hello"')
                        logger.debug('Attempt response')
##                        ars_response = (ars_resp('0002BF01', str(ahex(_rf_src))[2:-1], str(ahex(_dst_id))[2:-1], 1))
                        ars_response = (ars_resp('0002BF01', str(ahex(_rf_src))[2:-1], str(ahex(_dst_id))[2:-1], 1))
                        ars_snd = create_sms_seq(int_id(_rf_src), int_id(_dst_id), int_id(_dst_id), _slot, 1, ars_response[2] + ars_response[1] + ars_response[0])
                        for i in ars_snd:
                                                        # Sleep to prevent overflowing of Pi-Star buffer
                            sleep(pistar_overflow)
                            systems[UNIT_MAP[_rf_src][0]].send_system(i)
##                            systems['LOCAL'].send_system(i)
    
                else:
                    #NMEA GPS sentence
                    if '$GPRMC' in sms or '$GNRMC' in sms:
                        logger.debug(sms + '\n')
                        # Eliminate excess bytes based on NMEA type
                        # GPRMC
                        if 'GPRMC' in sms:
                            logger.debug('GPRMC location')
                            #nmea_parse = re.sub('A\*.*|.*\$', '', str(final_packet))
                            nmea_parse = re.sub('A\*.*|.*\$|\n.*', '', str(sms))
                        # GNRMC
                        if 'GNRMC' in sms:
                            logger.debug('GNRMC location')
                            nmea_parse = re.sub('.*\$|\n.*|V\*.*', '', sms)
                        loc = pynmea2.parse(nmea_parse, check=False)
                        logger.debug('Latitude: ' + str(loc.lat) + str(loc.lat_dir) + ' Longitude: ' + str(loc.lon) + str(loc.lon_dir) + ' Direction: ' + str(loc.true_course) + ' Speed: ' + str(loc.spd_over_grnd) + '\n')
                        if mirror == False:
                            try:
                                # Begin APRS format and upload
                                # Disable opening file for reading to reduce "collision" or reading and writing at same time.
                                # 14FRS2013 simplified and moved settings retrieval
                                user_settings = ast.literal_eval(os.popen('cat ' + user_settings_file).read())
                                logger.debug(user_settings)
                                if int_id(_rf_src) not in user_settings:	
                                    ssid = str(user_ssid)	
                                    icon_table = '/'	
                                    icon_icon = '['	
                                    comment = aprs_comment + ' DMR ID: ' + str(int_id(_rf_src)) 	
                                else:	
                                    if user_settings[int_id(_rf_src)][1]['ssid'] == '':	
                                        ssid = user_ssid	
                                    if user_settings[int_id(_rf_src)][3]['comment'] == '':	
                                        comment = aprs_comment + ' DMR ID: ' + str(int_id(_rf_src))	
                                    if user_settings[int_id(_rf_src)][2]['icon'] == '':	
                                        icon_table = '/'	
                                        icon_icon = '['	
                                    if user_settings[int_id(_rf_src)][2]['icon'] != '':	
                                        icon_table = user_settings[int_id(_rf_src)][2]['icon'][0]	
                                        icon_icon = user_settings[int_id(_rf_src)][2]['icon'][1]	
                                    if user_settings[int_id(_rf_src)][1]['ssid'] != '':	
                                        ssid = user_settings[int_id(_rf_src)][1]['ssid']	
                                    if user_settings[int_id(_rf_src)][3]['comment'] != '':	
                                        comment = user_settings[int_id(_rf_src)][3]['comment']	
                                aprs_loc_packet = str(get_alias(int_id(_rf_src), subscriber_ids)) + '-' + ssid + '>APHBL3,TCPIP*:@' + str(datetime.datetime.utcnow().strftime("%H%M%Sh")) + str(loc.lat[0:7]) + str(loc.lat_dir) + icon_table + str(loc.lon[0:8]) + str(loc.lon_dir) + icon_icon + str(round(loc.true_course)).zfill(3) + '/' + str(round(loc.spd_over_grnd)).zfill(3) + '/' + str(comment)
                                logger.debug(aprs_loc_packet)
                                logger.debug('User comment: ' + comment)
                                logger.debug('User SSID: ' + ssid)
                                logger.debug('User icon: ' + icon_table + icon_icon)
                            except Exception as error_exception:
                                logger.error('Error or user settings file not found, proceeding with default settings.')
                                aprs_loc_packet = str(get_alias(int_id(_rf_src), subscriber_ids)) + '-' + str(user_ssid) + '>APHBL3,TCPIP*:@' + str(datetime.datetime.utcnow().strftime("%H%M%Sh")) + str(loc.lat[0:7]) + str(loc.lat_dir) + '/' + str(loc.lon[0:8]) + str(loc.lon_dir) + '[' + str(round(loc.true_course)).zfill(3) + '/' + str(round(loc.spd_over_grnd)).zfill(3) + '/' + aprs_comment + ' DMR ID: ' + str(int_id(_rf_src))
                                logger.error(error_exception)
                                logger.error(str(traceback.extract_tb(error_exception.__traceback__)))
                            logger.info('APRS position packet generated')
                            try:
                            # Try parse of APRS packet. If it fails, it will not upload to APRS-IS
                                aprslib.parse(aprs_loc_packet)
                            # Float values of lat and lon. Anything that is not a number will cause it to fail.
                                float(loc.lat)
                                float(loc.lon)
        ##                        if int_id(_dst_id) == data_id:
                                if int_id(_dst_id) in data_id:
                                    dashboard_loc_write(str(get_alias(int_id(_rf_src), subscriber_ids)) + '-' + ssid, str(loc.lat[0:7]) + str(loc.lat_dir), str(loc.lon[0:8]) + str(loc.lon_dir), time(), comment, int_id(_rf_src))
                                    aprs_send(aprs_loc_packet)
                            except Exception as error_exception:
                                logger.error('Failed to parse packet. Packet may be deformed. Not uploaded.')
                                logger.error(error_exception)
                                logger.error(str(traceback.extract_tb(error_exception.__traceback__)))
                        # Get callsign based on DMR ID
                        # End APRS-IS upload
                    # Assume this is an SMS message
                    elif '$GPRMC' not in sms or '$GNRMC' not in sms:
                            logger.info('\nSMS detected. Attempting to parse.')
                            #logger.info(final_packet)
    ##                        logger.info('Attempting to find command...')
    ##                                sms = codecs.decode(bytes.fromhex(''.join(sms_hex[:-8].split('00'))), 'utf-8', 'ignore')
##                            sms = codecs.decode(bytes.fromhex(''.join(sms_hex_string[:-8].split('00'))), 'utf-8', 'ignore')
                            msg_found = re.sub('.*\n', '', sms)
                            logger.info('\n\n' + 'Received SMS from ' + str(get_alias(int_id(_rf_src), subscriber_ids)) + ', DMR ID: ' + str(int_id(_rf_src)) + ': ' + str(msg_found) + '\n')
                           
                            if int_id(_dst_id) in data_id:
                                process_sms(_rf_src, msg_found, _call_type, UNIT_MAP[_rf_src][0])
                            if int_id(_dst_id) not in data_id:
                                dashboard_sms_write(str(get_alias(int_id(_rf_src), subscriber_ids)), str(get_alias(int_id(_dst_id), subscriber_ids)), int_id(_dst_id), int_id(_rf_src), msg_found, time(), UNIT_MAP[_rf_src][0])
                                if '$' in msg_found[0:1]:
                                    send_sms(False, int_id(_dst_id), int_id(_rf_src), int_id(_rf_src), 'unit', msg_found)
                                    
                            pass

                # Reset assembly
                del packet_assembly[_rf_src]
                del btf[_rf_src]
                # Reset header type for next sequence
                del sub_hdr[_rf_src]



######

# Send data to all OBP connections that have an encryption key. Data such as subscribers are sent to other HBNet servers.
def svrd_send_all(_svrd_data):
    _svrd_packet = SVRD
    for system in CONFIG['SYSTEMS']:
        if CONFIG['SYSTEMS'][system]['ENABLED']:
                if CONFIG['SYSTEMS'][system]['MODE'] == 'OPENBRIDGE':
                    if CONFIG['SYSTEMS'][system]['ENCRYPTION_KEY'] != b'':
                        if b'UNIT' in _svrd_data:
                            logger.debug('Broadcasting gateway ID - SVRD ' + str(int_id(_svrd_data[4:])))
                        systems[system].send_system(_svrd_packet + _svrd_data)
def ten_loop_func():
    logger.info('10 minute loop')
    # Download user APRS settings
    if CONFIG['WEB_SERVICE']['REMOTE_CONFIG_ENABLED'] == True:
        with open(user_settings_file, 'w') as f:
                f.write(str(download_aprs_settings(CONFIG)))
        logger.info('Downloading and writing APRS settings file.')
    # Announce ID(s) over OBP
    for my_id in data_id:
        svrd_send_all(b'UNIT' + bytes_4(my_id))
    # Announce via MQTT
    mqtt_announce()
        
                       
    
def rule_timer_loop():
    global UNIT_MAP
    logger.debug('(ROUTER) routerHBP Rule timer loop started')
    _now = time()
    # Keep UNIT locations for 24 hours
    _then = _now - (3600 *24)
    remove_list = []
    for unit in UNIT_MAP:
        if UNIT_MAP[unit][1] < (_then):
            remove_list.append(unit)

    for unit in remove_list:
        del UNIT_MAP[unit]

    logger.debug('Removed unit(s) %s from UNIT_MAP', remove_list)
    if CONFIG['WEB_SERVICE']['REMOTE_CONFIG_ENABLED'] == True:
        ping(CONFIG)
        send_unit_table(CONFIG, UNIT_MAP)
        send_known_services(CONFIG, mqtt_services)
        send_que = send_sms_que_req(CONFIG)
        logger.debug(UNIT_MAP)
        try:
            for i in send_que:
                try:
                    send_sms(False, i['rcv_id'], data_id[0], data_id[0], i['call_type'],  i['msg'])
                except Exception as e:
                    logger.error('Error sending SMS in que to ' + str(i['rcv_id']) + ' - ' + i['msg'])
                    logger.error(e)
        except Exception as e:
            logger.error('Send que error')
            logger.error(e)

def peer_aprs_packets():
    for i in peer_aprs.items():
        for h in i[1].items():
            lat = decdeg2dms(float(h[1]['lat']))
            lon = decdeg2dms(float(h[1]['lon']))
            if lon[0] < 0:
                lon_dir = 'W'
            if lon[0] > 0:
                lon_dir = 'E'
            if lat[0] < 0:
                lat_dir = 'S'
            if lat[0] > 0:
                lat_dir = 'N'

            aprs_lat = str(str(re.sub('\..*|-', '', str(lat[0]))).zfill(2) + str(re.sub('\..*', '', str(lat[1])).zfill(2) + '.')) + str(re.sub('\..*', '', str(lat[2])).zfill(2)) + lat_dir
            aprs_lon = str(str(re.sub('\..*|-', '', str(lon[0]))).zfill(3) + str(re.sub('\..*', '', str(lon[1])).zfill(2) + '.')) + str(re.sub('\..*', '', str(lon[2])).zfill(2)) + lon_dir

            if len(str(h[0])) > 7:
                ending = int(str(h[0])[-2:])
                if ending in range(1, 25):
                    ssid = str(string.ascii_uppercase[ending - 1])
                else:
                    ssid = 'A'
            else:
                ssid = 'A'
            aprs_loc_packet = str(h[1]['call'] + '-' + ssid + '>APHBL3,TCPIP*:/' + str(datetime.datetime.utcnow().strftime("%H%M%Sh")) + str(aprs_lat) + '\\' + str(aprs_lon) + '&' + '/' + str(h[0]) + ' - '  + str(h[1]['description']))
            logger.debug(aprs_loc_packet)
            try:
                aprslib.parse(aprs_loc_packet)
                aprs_send(aprs_loc_packet)
            except Exception as e:
                logger.error(e)

##
##                print(lat)
####                print(lon)
    
class OBP(OPENBRIDGE):

    def __init__(self, _name, _config, _report):
        OPENBRIDGE.__init__(self, _name, _config, _report)


    def dmrd_received(self, _peer_id, _rf_src, _dst_id, _seq, _slot, _call_type, _frame_type, _dtype_vseq, _stream_id, _data):
        UNIT_MAP[_rf_src] = (self._system, time())
        if _rf_src not in PACKET_MATCH:
            PACKET_MATCH[_rf_src] = [_seq, time()]
        if _rf_src not in sub_hdr.keys():
            sub_hdr[_rf_src] = ''
            logger.debug('Added blank hdr')

        # Check to see if we have already received this packet
        elif _seq == PACKET_MATCH[_rf_src][0] and time() - 1 < PACKET_MATCH[_rf_src][1]:
            logger.debug('Packet matched, dropping: OBP')
            pass
        else:
            PACKET_MATCH[_rf_src] = [_seq, time()]
            logger.debug('OBP RCVD')
            if _dtype_vseq in [3,6,7] and _call_type == 'unit' or _call_type == 'group' and _dtype_vseq == 6 or _call_type == 'vcsbk':
                data_received(self, _peer_id, _rf_src, _dst_id, _seq, _slot, _call_type, _frame_type, _dtype_vseq, _stream_id, _data)
            else:
                pass       

    def svrd_received(self, _mode, _data):
        logger.debug('SVRD RCV')
        if _mode == b'UNIT':
            UNIT_MAP[_data] = (self._system, time())
        if _mode == b'APRS':
            peer_aprs[self._system] = ast.literal_eval(_data.decode('utf-8'))
            
        if _mode == b'DATA' or _mode == b'MDAT':
##            print(ahex(_data))
        # DMR Data packet, sent via SVRD
            _peer_id = _data[11:15]
            _seq = _data[4]
            _rf_src = _data[5:8]
            _dst_id = _data[8:11]
            _bits = _data[15]
            _slot = 2 if (_bits & 0x80) else 1
            #_call_type = 'unit' if (_bits & 0x40) else 'group'
            if _bits & 0x40:
                _call_type = 'unit'
            elif (_bits & 0x23) == 0x23:
                _call_type = 'vcsbk'
            else:
                _call_type = 'group'
            _frame_type = (_bits & 0x30) >> 4
            _dtype_vseq = (_bits & 0xF) # data, 1=voice header, 2=voice terminator; voice, 0=burst A ... 5=burst F
            _stream_id = _data[16:20]

##            print(int_id(_peer_id))
##            print(int_id(_rf_src))
##            print(int_id(_dst_id))
##            print((_dtype_vseq))
##            print(ahex(bptc_decode(_data)))
                       
            if _mode == b'MDAT' or _mode == b'DATA':
                logger.debug('MDAT')
                if _rf_src not in PACKET_MATCH:
                    PACKET_MATCH[_rf_src] = [_seq, time()]
                if _seq == PACKET_MATCH[_rf_src][0] and time() - 1 < PACKET_MATCH[_rf_src][1]:
                    logger.debug('Matched, dropping')
                    pass

                else:
                    if _mode == b'MDAT':
                        data_received(self, _peer_id, _rf_src, _dst_id, _seq, _slot, _call_type, _frame_type, _dtype_vseq, _stream_id, _data, True)
                    if _mode == b'DATA':
                        data_received(self, _peer_id, _rf_src, _dst_id, _seq, _slot, _call_type, _frame_type, _dtype_vseq, _stream_id, _data)



class HBP(HBSYSTEM):

    def __init__(self, _name, _config, _report):
        HBSYSTEM.__init__(self, _name, _config, _report)

    def dmrd_received(self, _peer_id, _rf_src, _dst_id, _seq, _slot, _call_type, _frame_type, _dtype_vseq, _stream_id, _data):
        UNIT_MAP[_rf_src] = (self._system, time())
     # Set data header type
        if _rf_src not in sub_hdr.keys():
            sub_hdr[_rf_src] = ''
            logger.debug('Added blank hdr')
##        logger.debug(ahex(_data))
        logger.debug('MMDVM RCVD')
        if _rf_src not in PACKET_MATCH:
            PACKET_MATCH[_rf_src] = [_data, time()]
        elif _data == PACKET_MATCH[_rf_src][0] and time() - 1 < PACKET_MATCH[_rf_src][1]:
            logger.debug('Packet matched, dropping: MMDVM')
            pass
        else:
            PACKET_MATCH[_rf_src] = [_data, time()]
##        try:
        if _dtype_vseq in [3,6,7] and _call_type == 'unit' or _call_type == 'group' and _dtype_vseq == 6 or _call_type == 'vcsbk':
            data_received(self, _peer_id, _rf_src, _dst_id, _seq, _slot, _call_type, _frame_type, _dtype_vseq, _stream_id, _data)
        else:
            pass
##        except Exception as e:
##            logger.error('Error, possibly received voice group call.')
##            logger.info(e)
##        pass



#************************************************
#      MAIN PROGRAM LOOP STARTS HERE
#************************************************

if __name__ == '__main__':

    import argparse
    import sys
    import os
    import signal

    # Change the current directory to the location of the application
    os.chdir(os.path.dirname(os.path.realpath(sys.argv[0])))

    # CLI argument parser - handles picking up the config file from the command line, and sending a "help" message
    parser = argparse.ArgumentParser()
    parser.add_argument('-c', '--config', action='store', dest='CONFIG_FILE', help='/full/path/to/config.file (usually data_gateway.cfg)')
    parser.add_argument('-l', '--logging', action='store', dest='LOG_LEVEL', help='Override config file logging level.')
    cli_args = parser.parse_args()

    # Ensure we have a path for the config file, if one wasn't specified, then use the default (top of file)
    if not cli_args.CONFIG_FILE:
        cli_args.CONFIG_FILE = os.path.dirname(os.path.abspath(__file__))+'/data_gateway.cfg'
      
    # Call the external routine to build the configuration dictionary
    CONFIG = data_gateway_config.build_config(cli_args.CONFIG_FILE)
    LOCAL_CONFIG = data_gateway_config.build_config(cli_args.CONFIG_FILE)


    if CONFIG['WEB_SERVICE']['REMOTE_CONFIG_ENABLED']:
        if CONFIG['WEB_SERVICE']['DASHBOARD_ONLY'] == False:
            CONFIG = download_config(CONFIG, cli_args.CONFIG_FILE)

    data_id_str = str('[' + CONFIG['DATA_CONFIG']['DATA_DMR_ID'] + ']')
    data_id = ast.literal_eval(data_id_str)
    

    # Group call or Unit (private) call
    call_type = CONFIG['DATA_CONFIG']['CALL_TYPE']
    # APRS-IS login information
    aprs_callsign = str(CONFIG['DATA_CONFIG']['APRS_LOGIN_CALL']).upper()
    aprs_passcode = int(CONFIG['DATA_CONFIG']['APRS_LOGIN_PASSCODE'])
    aprs_server = CONFIG['DATA_CONFIG']['APRS_SERVER']
    aprs_port = int(CONFIG['DATA_CONFIG']['APRS_PORT'])
    user_ssid = CONFIG['DATA_CONFIG']['USER_APRS_SSID']
    aprs_comment = CONFIG['DATA_CONFIG']['USER_APRS_COMMENT']
    aprs_filter = CONFIG['DATA_CONFIG']['APRS_FILTER']

  
    

##    # User APRS settings
    user_settings_file = CONFIG['DATA_CONFIG']['USER_SETTINGS_FILE']

    mqtt_shortcut_gen = CONFIG['DATA_CONFIG']['GATEWAY_CALLSIGN'].upper()

    

####    use_api = CONFIG['DATA_CONFIG']['USE_API']

    if CONFIG['WEB_SERVICE']['REMOTE_CONFIG_ENABLED'] == True:
        pass
    if CONFIG['WEB_SERVICE']['REMOTE_CONFIG_ENABLED'] == False:
        # Check if user_settings (for APRS settings of users) exists. Creat it if not.
        if Path(user_settings_file).is_file():
            pass
        else:
            Path(user_settings_file).touch()
            with open(user_settings_file, 'w') as user_dict_file:
                user_dict_file.write("{1: [{'call': 'N0CALL'}, {'ssid': ''}, {'icon': ''}, {'comment': ''}, {'pin': ''}, {'APRS': False}]}")
                user_dict_file.close()    

    # Start the system logger
    if cli_args.LOG_LEVEL:
        CONFIG['LOGGER']['LOG_LEVEL'] = cli_args.LOG_LEVEL
    logger = log.config_logging(CONFIG['LOGGER'])
    logger.info('\n\nCopyright (c) 2020, 2021\n\tKF7EEL - Eric, kf7eel@qsl.net -  All rights reserved.\n')
    logger.info('\n\nCopyright (c) 2013, 2014, 2015, 2016, 2018\n\tThe Regents of the K0USY Group. All rights reserved.\n')
    logger.debug('(GLOBAL) Logging system started, anything from here on gets logged')

    # Set up the signal handler
    def sig_handler(_signal, _frame):
        logger.info('(GLOBAL) SHUTDOWN: CONFBRIDGE IS TERMINATING WITH SIGNAL %s', str(_signal))
        hblink_handler(_signal, _frame)
        logger.info('(GLOBAL) SHUTDOWN: ALL SYSTEM HANDLERS EXECUTED - STOPPING REACTOR')
        reactor.stop()

    # Set signal handers so that we can gracefully exit if need be
    for sig in [signal.SIGINT, signal.SIGTERM]:
        signal.signal(sig, sig_handler)

    # Create the name-number mapping dictionaries
    peer_ids, subscriber_ids, talkgroup_ids = mk_aliases(CONFIG)

    # INITIALIZE THE REPORTING LOOP
    if CONFIG['REPORTS']['REPORT']:
        report_server = config_reports(CONFIG, reportFactory)
    else:
        report_server = None
        logger.info('(REPORT) TCP Socket reporting not configured')

    # HBlink instance creation
    logger.info('(GLOBAL) HBNet Data Gateway \'data_gateway.py\' -- SYSTEM STARTING...')
    for system in CONFIG['SYSTEMS']:
        if CONFIG['SYSTEMS'][system]['ENABLED']:
            if CONFIG['SYSTEMS'][system]['MODE'] == 'OPENBRIDGE':
                systems[system] = OBP(system, CONFIG, report_server)
            else:
                systems[system] = HBP(system, CONFIG, report_server)
            reactor.listenUDP(CONFIG['SYSTEMS'][system]['PORT'], systems[system], interface=CONFIG['SYSTEMS'][system]['IP'])
            logger.debug('(GLOBAL) %s instance created: %s, %s', CONFIG['SYSTEMS'][system]['MODE'], system, systems[system])

    def loopingErrHandle(failure):
        logger.error('(GLOBAL) STOPPING REACTOR TO AVOID MEMORY LEAK: Unhandled error in timed loop.\n %s', failure)
        reactor.stop()

    # Initialize the rule timer -- this if for user activated stuff
    rule_timer_task = task.LoopingCall(rule_timer_loop)
    rule_timer = rule_timer_task.start(10)
    rule_timer.addErrback(loopingErrHandle)

    # Experimental MQTT for external applications, etc.
    if CONFIG['DATA_CONFIG']['GATEWAY_CALLSIGN'] == 'n0call'.upper():
        logger.info('MQTT disabled. External applications and networks will not be available.')
    else:
        mqtt_thread = threading.Thread(target=mqtt_main, args=(CONFIG['DATA_CONFIG']['MQTT_USERNAME'],CONFIG['DATA_CONFIG']['MQTT_PASSWORD'],CONFIG['DATA_CONFIG']['MQTT_USERNAME2'],CONFIG['DATA_CONFIG']['MQTT_PASSWORD2'],CONFIG['DATA_CONFIG']['MQTT_SERVER'],int(CONFIG['DATA_CONFIG']['MQTT_PORT']),CONFIG['DATA_CONFIG']['MQTT_SERVER2'],int(CONFIG['DATA_CONFIG']['MQTT_PORT2']),))
        mqtt_thread.daemon = True
        mqtt_thread.start()

    # Used for misc timing events
    ten_loop_task = task.LoopingCall(ten_loop_func)
    ten_loop = ten_loop_task.start(600)
    ten_loop.addErrback(loopingErrHandle)

    if Path('./subscriber_sms_formats.txt').is_file():
        pass
    else:
        Path('./subscriber_sms_formats.txt').touch()
        with open('./subscriber_sms_formats.txt', 'w') as sub_form_file:
                sub_form_file.write("{b'01':'motorola'}")
                sub_form_file.close() 

    if 'N0CALL' in aprs_callsign:
        logger.info('APRS callsign set to N0CALL, packet not sent.')
        pass
    else:
        aprs_thread = threading.Thread(target=aprs_rx, args=(aprs_callsign, aprs_passcode, aprs_server, aprs_port, aprs_filter, user_ssid,))
        aprs_thread.daemon = True
        aprs_thread.start()
    # Create folder so hbnet.py can access list PEER connections
    if Path('/tmp/' + (CONFIG['LOGGER']['LOG_NAME'] + '_PEERS/')).exists():
        pass
    else:
        Path('/tmp/' + (CONFIG['LOGGER']['LOG_NAME'] + '_PEERS/')).mkdir()
    reactor.run()

# John 3:16 - For God so loved the world, that he gave his only Son,
# that whoever believes in him should not perish but have eternal life.
