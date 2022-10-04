#!/usr/bin/env python
#
###############################################################################
#   Copyright (C) 2016-2019  Cortney T. Buffington, N0MJS <n0mjs@me.com> (and Mike Zingman N4IRR)
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


# Python modules we need
import sys
from bitarray import bitarray
from time import time, sleep
from importlib import import_module

# Twisted is pretty important, so I keep it separate
from twisted.internet.protocol import Factory, Protocol
from twisted.protocols.basic import NetstringReceiver
from twisted.internet import reactor, task

# Things we import from the main hblink module
from hblink import HBSYSTEM, systems, hblink_handler, reportFactory, REPORT_OPCODES, config_reports, mk_aliases
from dmr_utils3.utils import bytes_3, int_id, get_alias
from dmr_utils3 import decode, bptc, const
import config
import log
import const

from binascii import b2a_hex as ahex


import random
import ast
import os

# The module needs logging logging, but handlers, etc. are controlled by the parent
import logging
logger = logging.getLogger(__name__)

from pathlib import Path



# Does anybody read this stuff? There's a PEP somewhere that says I should do this.
__author__     = 'Cortney T. Buffington, N0MJS and Mike Zingman, N4IRR'
__copyright__  = 'Copyright (c) 2016-2019 Cortney T. Buffington, N0MJS and the K0USY Group'
__license__    = 'GNU GPLv3'
__maintainer__ = 'Cort Buffington, N0MJS'
__email__      = 'n0mjs@me.com'
__status__     = 'pre-alpha'


COMMAND = {
    'record_unit' : 35,
    'play_unit': 33,
    'delete_unit':39

}

def command_check(dmr_id):
    dmr_id = int_id(dmr_id)
    mode = False
    for i in COMMAND.items():
        if dmr_id == i[1]:
            mode = True
            return mode
    return mode


def delete_file(dmr_id):
    os.remove('playback/' + str(dmr_id) + '.data')
    # print('remove file')
    logger.info('File removed')

def write_file(lst, dmr_id):
    # with open('playback_test/' + str(random.randint(1,99)) + '.seq', 'w') as peer_file:
    try:
        data = ast.literal_eval(os.popen('cat playback/' + str(dmr_id) + '.data').read())
    except:
        data = []
    #     pass
    # new_lst = data + lst
    data.append(lst)
    if not Path('playback/' + str(dmr_id) + '.data').is_file():
        Path('playback/' + str(dmr_id) + '.data').touch()

    with open('playback/' + str(dmr_id) + '.data', 'w') as peer_file:
        peer_file.write(str(data))
        peer_file.close()

def play(dmr_id):
    # data = os.popen('cat playback_test/' + str(seq_file) + '.seq').read()
    try:
        data = ast.literal_eval(os.popen('cat playback/' + str(dmr_id) + '.data').read())
    except:
        data = []
        logger.error('No messages or other error.')
    # print(data)
    # print(data)
    # with open('playback_test/' + str(dmr_id) + '.data', 'w') as peer_file:
    #     peer_file.write(str([]))
    #     peer_file.close()
    return data


# DST_DICT = {}
REC_DICT = {}
# PLAY_DICT = {}

# Module gobal varaibles

# class OBP(OPENBRIDGE):

#     def __init__(self, _name, _config, _report):
#         OPENBRIDGE.__init__(self, _name, _config, _report)


#     def dmrd_received(self, _peer_id, _rf_src, _dst_id, _seq, _slot, _call_type, _frame_type, _dtype_vseq, _stream_id, _data):
#         playback().dmrd_received(self, _peer_id, _rf_src, _dst_id, _seq, _slot, _call_type, _frame_type, _dtype_vseq, _stream_id, _data)
#         pass

class playback(HBSYSTEM):

    def __init__(self, _name, _config, _report):
        HBSYSTEM.__init__(self, _name, _config, _report)

        # Status information for the system, TS1 & TS2
        # 1 & 2 are "timeslot"
        # In TX_EMB_LC, 2-5 are burst B-E
        self.STATUS = {
            1: {
                'RX_START':     time(),
                'RX_SEQ':       '\x00',
                'RX_RFS':       '\x00',
                'TX_RFS':       '\x00',
                'RX_STREAM_ID': '\x00',
                'TX_STREAM_ID': '\x00',
                'RX_TGID':      '\x00\x00\x00',
                'TX_TGID':      '\x00\x00\x00',
                'RX_TIME':      time(),
                'TX_TIME':      time(),
                'RX_TYPE':      const.HBPF_SLT_VTERM,
                'RX_LC':        '\x00',
                'TX_H_LC':      '\x00',
                'TX_T_LC':      '\x00',
                'TX_EMB_LC': {
                    1: '\x00',
                    2: '\x00',
                    3: '\x00',
                    4: '\x00',
                }
                },
            2: {
                'RX_START':     time(),
                'RX_SEQ':       '\x00',
                'RX_RFS':       '\x00',
                'TX_RFS':       '\x00',
                'RX_STREAM_ID': '\x00',
                'TX_STREAM_ID': '\x00',
                'RX_TGID':      '\x00\x00\x00',
                'TX_TGID':      '\x00\x00\x00',
                'RX_TIME':      time(),
                'TX_TIME':      time(),
                'RX_TYPE':      const.HBPF_SLT_VTERM,
                'RX_LC':        '\x00',
                'TX_H_LC':      '\x00',
                'TX_T_LC':      '\x00',
                'TX_EMB_LC': {
                    1: '\x00',
                    2: '\x00',
                    3: '\x00',
                    4: '\x00',
                }
            }
        }
        self.CALL_DATA = []

    def dmrd_received(self, _peer_id, _rf_src, _dst_id, _seq, _slot, _call_type, _frame_type, _dtype_vseq, _stream_id, _data):
        pkt_time = time()
        dmrpkt = _data[20:53]
        _bits = _data[15]

        # REC_DICT[int_id(_rf_src)] = False

        # print(self.STATUS)

        try:
            REC_DICT[int_id(_rf_src)]
            # print(REC_DICT[int_id(_rf_src)])
        except:
            REC_DICT[int_id(_rf_src)] = False

        # print(_call_type)
        # print(not command_check(_dst_id))

        if _call_type == 'unit':
            # print(self.STATUS[_slot]['RX_STREAM_ID'])

            # To prevent the recording stuff from ignoring packets due to same stream ID,
            # Only keep track of stream start when matching _dst_id is correct
            # print(int_id(_dst_id))
            if command_check(_dst_id):
                # print('matches')
                logger.info('UNIT call, first packet, checking commands...')

                # Start of stream
                if (_stream_id != self.STATUS[_slot]['RX_STREAM_ID']):
                    self.STATUS['RX_START'] = pkt_time
                    # logger.info('(%s) *START RECORDING UNIT CALL* STREAM ID: %s SUB: %s (%s) REPEATER: %s (%s) TGID %s (%s), TS %s', \
                    #                   self._system, int_id(_stream_id), get_alias(_rf_src, subscriber_ids), int_id(_rf_src), get_alias(_peer_id, peer_ids), int_id(_peer_id), get_alias(_dst_id, talkgroup_ids), int_id(_dst_id), _slot)
                    # self.CALL_DATA.append(_data)
                    self.STATUS[_slot]['RX_STREAM_ID'] = _stream_id

            #         print('PKT start')

            #         print(int_id(_dst_id))

                    # UNIT call ID options here
                    if int_id(_dst_id) == COMMAND['record_unit']:
                        REC_DICT[int_id(_rf_src)] = True
                        logger.info('Next transmission from ' + str(int_id(_rf_src)) + ' will be saved.')

                    elif int_id(_dst_id) == COMMAND['play_unit']:
                        # _play_seq = play(int_id(_rf_src))
                        # print('play')
                        logger.info('Playback started for ' + str(int_id(_rf_src)))
                        # print(_play_seq)
                        n = 0
                        for i in play(int_id(_rf_src)):
                            sleep(2)
                            # print(i)
                            n = n + 1
                            logger.info('Playing message ' + str(n))
                            for r in i:
                                self.send_system(r)
                                sleep(0.06)
                        logger.info('Finished')
                    elif int_id(_dst_id) == COMMAND['delete_unit']:
                        delete_file(int_id(_rf_src))
                        logger.info('Deleting all messages for ' + str(int_id(_rf_src)))







        #     # Final actions - Is this a voice terminator?
        #     # if (_frame_type == const.HBPF_DATA_SYNC) and (_dtype_vseq == const.HBPF_SLT_VTERM) and (self.STATUS[_slot]['RX_TYPE'] != const.HBPF_SLT_VTERM) and (self.CALL_DATA):
        #     #     call_duration = pkt_time - self.STATUS['RX_START']
        #     #     # self.CALL_DATA.append(_data)
        #     #     # logger.info('(%s) *END   RECORDING UNIT CALL* STREAM ID: %s', self._system, int_id(_stream_id))
        #     #     print('PKT END')

        #     # print('unit')

        #     # if int_id(_dst_id) == 91:
        #     #     REC_DICT[int_id(_rf_src)] = True

        #     # elif int_id(_dst_id) == 90:
        #     #     _play_seq = play(int_id(_rf_src))
        #     #     for i in _play_seq:
        #     #         self.send_system(i)
        #     #         sleep(0.06)
        #     #     _play_seq = []





        #     # # # Is this is a new call stream?
        #     # if (_stream_id != self.STATUS[_slot]['RX_STREAM_ID']):
        #     #     self.STATUS['RX_START'] = pkt_time
        #     #     self.STATUS[_slot]['RX_STREAM_ID'] = _stream_id
        #     #     return

        #     # if (_stream_id not in self.STATUS):
        #     #     # This is a new call stream
        #     #     self.STATUS[_stream_id] = {
        #     #         'START':     pkt_time,
        #     #         'CONTENTION':False,
        #     #         'RFS':       _rf_src,
        #     #         'TYPE':      'UNIT',
        #     #         'DST':       _dst_id,
        #     #         'ACTIVE':    True
        #     #     }

        #     # # if (_frame_type == const.HBPF_DATA_SYNC) and (_dtype_vseq == const.HBPF_SLT_VTERM) and (self.STATUS[_slot]['RX_TYPE'] != const.HBPF_SLT_VTERM) and (self.CALL_DATA):
        #     # #     call_duration = pkt_time - self.STATUS['RX_START']
        #     # #     print(call_duration)
        #     #         # Final actions - Is this a voice terminator?
        #     # if (_frame_type == const.HBPF_DATA_SYNC) and (_dtype_vseq == const.HBPF_SLT_VTERM) and (self.STATUS[_slot]['RX_TYPE'] != const.HBPF_SLT_VTERM):
        #     #     self._targets = []
        #     #     call_duration = pkt_time - self.STATUS[_slot]['RX_START']
        #     #     print(call_duration)
            

        #     # print(int_id(_dst_id))
        #     # print(ahex(_dst_id))
        #     # print(ahex(_stream_id))
        #     # try:
        #     #     print(pkt_time - DST_DICT[int_id(_dst_id)][0] < 5)
        #     #     print(DST_DICT[int_id(_dst_id)][1] != (_stream_id))
        #     #     print(DST_DICT[int_id(_dst_id)][1])
        #     #     # print(pkt_time)
        #     #     # print(DST_DICT[int_id(_dst_id)])
        #     #     if pkt_time - DST_DICT[int_id(_dst_id)][0] < 5 and DST_DICT[int_id(_dst_id)][1] != (_stream_id):
        #     #         print('true -------------------')
        #     #     else:
        #     #         del DST_DICT[int_id(_dst_id)]
        #     # except:
        #     #     DST_DICT[int_id(_dst_id)] = [pkt_time, (_stream_id)]
        #     # if len(str(int_id(_dst_id))) > 7:
        #     #     _mode = int(str(int_id(_dst_id))[7:])
        #     #     _dst = int(str(int_id(_dst_id))[:7])
        #     #     print(_dst)
        #     #     # print(_mode)
        #     #     if _mode == 1:
        #     #         REC_DICT[int_id(_rf_src)] = _dst
        #     #         # print('rec')
        #     #         # _play_seq = play(50)
        #     #         # for i in _play_seq:
        #     #         #     self.send_system(i)
        #     #         #     sleep(0.06)
        #     #         # os.remove('playback_test/50.seq')

        # # elif int_id(_dst_id) == 9:
        # #     print(int_id(_dst_id))

        if _call_type == 'group' or _call_type == 'unit' and REC_DICT[int_id(_rf_src)] == True: # and int_id(_dst_id) != COMMAND['record_unit']:
        # if _call_type == 'group' or _call_type == 'unit' and REC_DICT[int_id(_rf_src)] == True and not command_check(_dst_id):

        # if _call_type == 'group' or _call_type == 'unit': # and REC_DICT[int_id(_rf_src)] == True and int_id(_dst_id) != 91:
            # print(self.STATUS[_slot]['RX_STREAM_ID'])
            # _dst_id = bytes_3(int(str(int_id(_dst_id))[:7]))
            # print(ahex(_data))
            
            # Is this is a new call stream?
            if (_stream_id != self.STATUS[_slot]['RX_STREAM_ID']):
                self.STATUS['RX_START'] = pkt_time
                logger.info('(%s) *START RECORDING* STREAM ID: %s SUB: %s (%s) REPEATER: %s (%s) TGID %s (%s), TS %s', \
                                  self._system, int_id(_stream_id), get_alias(_rf_src, subscriber_ids), int_id(_rf_src), get_alias(_peer_id, peer_ids), int_id(_peer_id), get_alias(_dst_id, talkgroup_ids), int_id(_dst_id), _slot)
                self.CALL_DATA.append(_data)
                self.STATUS[_slot]['RX_STREAM_ID'] = _stream_id
                print(ahex(_stream_id))
                return

            # Final actions - Is this a voice terminator?
            if (_frame_type == const.HBPF_DATA_SYNC) and (_dtype_vseq == const.HBPF_SLT_VTERM) and (self.STATUS[_slot]['RX_TYPE'] != const.HBPF_SLT_VTERM) and (self.CALL_DATA):
                call_duration = pkt_time - self.STATUS['RX_START']
                self.CALL_DATA.append(_data)
                logger.info('(%s) *END   RECORDING* STREAM ID: %s', self._system, int_id(_stream_id))
                sleep(2)
                logger.info('(%s) *START  PLAYBACK* STREAM ID: %s SUB: %s (%s) REPEATER: %s (%s) TGID %s (%s), TS %s, Duration: %s', \
                                  self._system, int_id(_stream_id), get_alias(_rf_src, subscriber_ids), int_id(_rf_src), get_alias(_peer_id, peer_ids), int_id(_peer_id), get_alias(_dst_id, talkgroup_ids), int_id(_dst_id), _slot, call_duration)
                # if _call_type != 'unit':
                for i in self.CALL_DATA:
                    self.send_system(i)
                    #print(i)
                    sleep(0.06)
                # print(REC_DICT[int_id(_rf_src)])
                if REC_DICT[int_id(_rf_src)] == True:
                    logger.info('RF Source matches record command, saving for ' + str(int_id(_dst_id)) + ', ' + _call_type)
                    write_file(self.CALL_DATA, int_id(_dst_id))

                    REC_DICT[int_id(_rf_src)] = False

                # print(self.CALL_DATA)
                # try:
                #     print(REC_DICT)
                #     print(REC_DICT[int_id(_rf_src)])
                # except:
                #     print('nope')
                # if int_id(_dst_id) == 9:
                #     for i in play(91):
                #         self.send_system(i)
                #         sleep(0.06)
                #         print(i)
                # write_file(self.CALL_DATA)
                self.CALL_DATA = []
                logger.info('(%s) *END    PLAYBACK* STREAM ID: %s', self._system, int_id(_stream_id))

            else:
                if self.CALL_DATA:
                    self.CALL_DATA.append(_data)


            # Mark status variables for use later
            self.STATUS[_slot]['RX_RFS']       = _rf_src
            self.STATUS[_slot]['RX_TYPE']      = _dtype_vseq
            self.STATUS[_slot]['RX_TGID']      = _dst_id
            self.STATUS[_slot]['RX_TIME']      = pkt_time
            self.STATUS[_slot]['RX_STREAM_ID'] = _stream_id


#************************************************
#      MAIN PROGRAM LOOP STARTS HERE
#************************************************

if __name__ == '__main__':
    
    import argparse
    import sys
    import os
    import signal
    from dmr_utils3.utils import try_download, mk_id_dict
    
    # Change the current directory to the location of the application
    os.chdir(os.path.dirname(os.path.realpath(sys.argv[0])))

    # CLI argument parser - handles picking up the config file from the command line, and sending a "help" message
    parser = argparse.ArgumentParser()
    parser.add_argument('-c', '--config', action='store', dest='CONFIG_FILE', help='/full/path/to/config.file (usually hblink.cfg)')
    parser.add_argument('-l', '--logging', action='store', dest='LOG_LEVEL', help='Override config file logging level.')
    cli_args = parser.parse_args()

    # Ensure we have a path for the config file, if one wasn't specified, then use the default (top of file)
    if not cli_args.CONFIG_FILE:
        cli_args.CONFIG_FILE = os.path.dirname(os.path.abspath(__file__))+'/hblink.cfg'

    # Call the external routine to build the configuration dictionary
    CONFIG = config.build_config(cli_args.CONFIG_FILE)
    
    # Start the system logger
    if cli_args.LOG_LEVEL:
        CONFIG['LOGGER']['LOG_LEVEL'] = cli_args.LOG_LEVEL
    logger = log.config_logging(CONFIG['LOGGER'])
    logger.info('\n\nVoicemail/Annaouncment/Echo Server additions, Copyright (c) 2022\n\tKF7EEL - Eric, kf7eel@qsl.net -  All rights reserved.\n')
    logger.info('\n\nCopyright (c) 2013, 2014, 2015, 2016, 2018, 2019\n\tThe Founding Members of the K0USY Group. All rights reserved.\n')
    logger.debug('Logging system started, anything from here on gets logged')
    
    # Set up the signal handler
    def sig_handler(_signal, _frame):
        logger.info('SHUTDOWN: HBROUTER IS TERMINATING WITH SIGNAL %s', str(_signal))
        hblink_handler(_signal, _frame)
        logger.info('SHUTDOWN: ALL SYSTEM HANDLERS EXECUTED - STOPPING REACTOR')
        reactor.stop()
        
    # Set signal handers so that we can gracefully exit if need be
    for sig in [signal.SIGTERM, signal.SIGINT]:
        signal.signal(sig, sig_handler)
    
    # ID ALIAS CREATION
    # Download
    if CONFIG['ALIASES']['TRY_DOWNLOAD'] == True:
        # Try updating peer aliases file
        result = try_download(CONFIG['ALIASES']['PATH'], CONFIG['ALIASES']['PEER_FILE'], CONFIG['ALIASES']['PEER_URL'], CONFIG['ALIASES']['STALE_TIME'])
        logger.info(result)
        # Try updating subscriber aliases file
        result = try_download(CONFIG['ALIASES']['PATH'], CONFIG['ALIASES']['SUBSCRIBER_FILE'], CONFIG['ALIASES']['SUBSCRIBER_URL'], CONFIG['ALIASES']['STALE_TIME'])
        logger.info(result)
        
    # Create the name-number mapping dictionaries
    peer_ids, subscriber_ids, talkgroup_ids = mk_aliases(CONFIG)
        
    # INITIALIZE THE REPORTING LOOP
    report_server = config_reports(CONFIG, reportFactory)

    # Create folder so hbnet.py can access list PEER connections
    # print(CONFIG['LOGGER']['LOG_NAME'])
    if Path('/tmp/' + (CONFIG['LOGGER']['LOG_NAME'] + '_PEERS/')).exists():
        pass
    else:
        Path('/tmp/' + (CONFIG['LOGGER']['LOG_NAME'] + '_PEERS/')).mkdir()
    
    if Path('playback/').exists():
        pass
    else:
        Path('playback/').mkdir()
    
    
    # HBlink instance creation
    logger.info('HBlink \'playback.py\' (c) 2017-2019 Cort Buffington, N0MJS & Mike Zingman, N4IRR -- SYSTEM STARTING...')
    for system in CONFIG['SYSTEMS']:
        if CONFIG['SYSTEMS'][system]['ENABLED']:
            if CONFIG['SYSTEMS'][system]['MODE'] == 'OPENBRIDGE':
                logger.critical('%s FATAL: Instance is mode \'OPENBRIDGE\', \n\t\t...Which would be tragic for playback, since it carries multiple call\n\t\tstreams simultaneously. playback.py onlyl works with MMDVM-based systems', system)
                sys.exit('playback.py cannot function with systems that are not MMDVM devices. System {} is configured as an OPENBRIDGE'.format(system))
            else:
                systems[system] = playback(system, CONFIG, report_server)
            reactor.listenUDP(CONFIG['SYSTEMS'][system]['PORT'], systems[system], interface=CONFIG['SYSTEMS'][system]['IP'])
            logger.debug('%s instance created: %s, %s', CONFIG['SYSTEMS'][system]['MODE'], system, systems[system])
    reactor.run()
