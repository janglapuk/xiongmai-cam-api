import sys, time
import xmconst
import json, os, subprocess, socket
from struct import pack, unpack
from pprint import pprint, pformat

if sys.version_info[0] == 2:
    from threading import _Timer as Timer
else:
    from threading import Timer

class RepeatingTimer(Timer):
    def run(self):
        while not self.finished.is_set():
            self.function(*self.args, **self.kwargs)
            self.finished.wait(self.interval)

class XMCam:
    instance = None
    main_socket = None
    socket_timeout = 20
    sid = 0
    sequence = 0
    ip = ''
    port = 0
    username = password = ''
    keepalive_timer = None

    def __init__(self, ip, port, username, password, sid=0, autoconnect=True, instance=None):
        self.ip = ip
        self.port = port
        self.username = username
        self.password = password
        self.sid = sid
        self.instance = instance

        if autoconnect:
            self.connect()

    def __del__(self):
        try:
            self.disconnect()
        except:
            pass

    def is_sub_connection(self):
        return self.instance != None
        
    def connect(self):
        try:
            self.main_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.main_socket.settimeout(self.socket_timeout)
            self.main_socket.connect((self.ip, self.port))
        except Exception as e:
            print(e)
            return False
        return True

    def disconnect(self):
        try:
            self.main_socket.close()
            self._stop_keepalive_interval()
        except:
            pass

    @staticmethod
    def prettify(json_data):
        data_dict = json.loads(json_data)
        return pformat(data_dict)

    @staticmethod
    def to_dict(json_data):
        data_dict = json.loads(json_data)
        return data_dict

    def _generic_command_head(self, msgid, params):
        pkt = params

        if msgid != xmconst.LOGIN_REQ2 and type(params) != bytes:
            pkt['SessionID'] = self._build_packet_sid()

        cmd_data = self._build_packet(msgid, pkt)
        self.main_socket.send(cmd_data)

        if type(params) == bytes:
            return cmd_data    

        response_head = self._get_response_head()
        return response_head
        
    def _generic_command(self, msgid, params):
        response_head = self._generic_command_head(msgid, params)
        out = self._get_response_data(response_head)

        if msgid == xmconst.LOGIN_REQ2 and 'SessionID' in response_head:
            self.sid = response_head['SessionID']

        if out:
            return out

        return None

    def _generic_command_download(self, msgid, params, file):
        reply_head = self._generic_command_head(msgid, params)
        out = self._get_response_data(reply_head)

        if out:
            with open(file, 'wb') as f:
                f.write(out)
            return True

        return False

    def _get_response_head(self):
        data = self.main_socket.recv(4)
        head_flag, version, _, _ = unpack('BBBB', data)

        data = self.main_socket.recv(8)
        sid, seq = unpack('ii', data)

        data = self.main_socket.recv(8)
        channel, endflag, msgid, size = unpack('BBHI', data)

        reply_head = {
            'Version': version,
            'SessionID': sid,
            'Sequence': seq,
            'MessageId': msgid,
            'Content_Length': size
        }

        self.sequence = seq

        return reply_head

    def _get_response_data(self, reply_head):
        reply = reply_head
        length = reply['Content_Length']
        out = ''

        for i in range(0, length):
            data = self.main_socket.recv(1)
            out += data.decode('utf-8')

        return out.rstrip('\x00')

    def _build_packet_sid(self):
        return '0x%08x' % self.sid

    def _build_packet(self, ptype, data):
        pkt_type = ptype
        pkt_prefix_1 = (0xff, 0x01, 0x00, 0x00)
        pkt_prefix_2 = (0x00, 0x00, 0x00, 0x00)

        header = pack('B'*len(pkt_prefix_1), *pkt_prefix_1)
        header += pack('I', self.sid)
        header += pack('B'*len(pkt_prefix_2), *pkt_prefix_2)
        header += pack('H', 0) + pack('H', pkt_type)

        # If data is bytes, designed for sending stream bytes to server
        if type(data) == bytes:
            pkt_data = data
            pkt_data = header + pack('I', len(pkt_data)) + pkt_data
        else:
            pkt_data = json.dumps(data)
            pkt_data = header + pack('I', len(pkt_data)) + bytes(pkt_data.encode('ascii'))

        return pkt_data

    def _start_keepalive_interval(self):
        self.keepalive_timer = RepeatingTimer(20.0, self._interval_keepalive)
        self.keepalive_timer.start()

    def _stop_keepalive_interval(self):
        if self.keepalive_timer != None:
            self.keepalive_timer.cancel()

    def _interval_keepalive(self):
        pkt = { 
            "Name" : "KeepAlive" 
        }
        response = self._generic_command(xmconst.KEEPALIVE_REQ, pkt)
        print(response)

    def create_sub_connection(self, autoconnect=False):
        subconn = XMCam(self.ip, self.port, self.username, self.password, sid=self.sid, instance=self, autoconnect=autoconnect)
        return subconn

    def cmd_login(self):
        pkt = {
            'EncryptType': 'MD5',
            'LoginType': 'DVRIP-Web',
            'PassWord': self.sofia_hash(self.password),
            'UserName': self.username
        }

        response = self._generic_command(xmconst.LOGIN_REQ2, pkt)
        respdict = self.to_dict(response)

        if not self.is_sub_connection() and respdict != None and 'Ret' in respdict and respdict['Ret'] == 100:
            self._start_keepalive_interval()
        else:
            print(__name__, 'Cannot start keepalive')

        return response

    def cmd_system_function(self):
        pkt = {
            'Name': 'SystemFunction'
        }

        response = self._generic_command(xmconst.ABILITY_GET, pkt)
        return self.prettify(response)

    def cmd_system_info(self):
        pkt = {
            'Name': 'SystemInfo'
        }

        response = self._generic_command(xmconst.SYSINFO_REQ, pkt)
        return self.prettify(response)

    def cmd_keep_alive(self):
        pkt = {
            'Name': 'KeepAlive'
        }

        return self._generic_command(xmconst.KEEPALIVE_REQ, pkt)

    def cmd_channel_title(self):
        pkt = {
            'Name': 'ChannelTitle'
        }

        response = self._generic_command(xmconst.CONFIG_CHANNELTILE_GET, pkt)
        return self.prettify(response)

    def cmd_OEM_info(self):
        pkt = {
            'Name': 'OEMInfo'
        }

        response = self._generic_command(xmconst.SYSINFO_REQ, pkt)
        return self.prettify(response)

    def cmd_storage_info(self):
        pkt = {
            'Name': 'StorageInfo'
        }

        response = self._generic_command(xmconst.SYSINFO_REQ, pkt)
        return self.prettify(response)

    def cmd_sync_time(self, noRTC = False):
        cmd = 'OPTimeSetting'
        pkt_type = xmconst.SYSMANAGER_REQ

        if noRTC:
            cmd += 'NoRTC'
            pkt_type = xmconst.SYNC_TIME_REQ

        pkt = {
            'Name': cmd,
            cmd: time.strftime('%Y-%m-%d %H:%M:%S')
        }

        response = self._generic_command(pkt_type, pkt)
        return response

    def cmd_get_time(self):
        pkt = {
            'Name': 'OPTimeQuery'
        }

        response = self._generic_command(xmconst.TIMEQUERY_REQ, pkt)
        return response

    def cmd_users(self):
        pkt = {

        }

        response = self._generic_command(xmconst.USERS_GET, pkt)
        return self.prettify(response)

    def cmd_ptz_control(self, direction, stop=False):
        pkt = {
            "Name":	"OPPTZControl",
            "OPPTZControl":	{
                "Command":	direction, #DirectionLeft, DirectionRight, DirectionUp, DirectionDown
                "Parameter":	{
                    "AUX":	{
                        "Number": 0,
                        "Status": "On"
                    },
                    "Channel": 0,
                    "MenuOpts":	"Enter",
                    "POINT": {
                        "bottom": 0,
                        "left":	0,
                        "right": 0,
                        "top": 0
                    },
                    "Pattern": "Start", #""SetBegin",
                    "Preset": -1 if stop else 65535,
                    "Step": 30,
                    "Tour": 0
                }
            }
        }

        response = self._generic_command(xmconst.PTZ_REQ, pkt)
        return self.prettify(response)

    def cmd_photo(self, file):
        pkt = {

        }

        reply = self._generic_command_download(xmconst.PHOTO_GET_REQ, pkt, file)
        return reply

    def cmd_config_export(self, file):
        pkt = {
            'Name': ''
        }

        reply = self._generic_command_download(xmconst.CONFIG_EXPORT_REQ, pkt, file)
        return reply

    # Just because no snap command supported, we need external program to capture from RTSP stream
    # using avconv or ffmpeg
    @staticmethod
    def cmd_external_snap(snap_file, app='/usr/bin/ffmpeg',
                          rtsp='rtsp://192.168.1.10/user=admin&password=admin&channel=1&stream=0.sdp',
                          args=('-y', '-f', 'image2', '-vframes', '1', '-pix_fmt', 'yuvj420p')):

        if not os.path.exists(app):
            return False

        # Add executable
        fullargs = [app]

        # Make silent except errors
        fullargs.append('-loglevel')
        fullargs.append('panic')

        # Append input arg
        fullargs.append('-i')
        fullargs.append(rtsp)

        # Append other args
        [fullargs.append(a) for a in args]

        # Lastly, append output arg
        fullargs.append(snap_file)

        # child = subprocess.Popen(process, stdout=subprocess.PIPE)
        child = subprocess.Popen(fullargs)
        child.communicate()

        return child.returncode == 0 # True if 0

    @staticmethod
    def cmd_external_record(video_file, app='/usr/bin/ffmpeg',
                            rtsp='rtsp://192.168.1.10/user=admin&password=admin&channel=1&stream=0.sdp',
                            args=('-vcodec', 'copy', '-f', 'mp4', '-y', '-an'),
                            time_limit=5
                            ):
        if not os.path.exists(app):
            return False

        # Add executable
        fullargs = [app]

        # Make silent except errors
        fullargs.append('-loglevel')
        fullargs.append('panic')

        # Append input arg
        fullargs.append('-i')
        fullargs.append(rtsp)

        # Append other args
        [fullargs.append(a) for a in args]

        # Append record time limit in secs
        fullargs.append('-t')
        fullargs.append(str(time_limit) if time_limit > 0 else '5')

        # Append output arg
        fullargs.append(video_file)

        # child = subprocess.Popen(process, stdout=subprocess.PIPE)
        child = subprocess.Popen(fullargs)
        child.communicate()

        return child.returncode == 0 # True if 0

    @staticmethod
    def cmd_snap(snap_file):
        retval = XMCam.cmd_external_snap(snap_file)
        return retval

    def cmd_talk_claim(self):
        assert self.is_sub_connection(), 'cmd_talk_claim need run on a sub connection'

        pkt = { 
            "Name": "OPTalk", 
            "OPTalk": { 
                "Action": "Claim", 
                "AudioFormat": { 
                    "BitRate": 0, 
                    "EncodeType": "G711_ALAW", 
                    "SampleBit": 8, 
                    "SampleRate": 8 
                } 
            }
        }

        response = self._generic_command(xmconst.TALK_CLAIM, pkt)
        return response

    def cmd_talk_send_stream(self, data):
        #assert type(data) == bytes, 'Data should be a PCM bytes type'
        # final_data = bytes.fromhex('000001fa0e024001') + data
        final_data = b'\x00\x00\x01\xfa\x0e\x02\x40\x01' + data
        sent = self._generic_command_head(xmconst.TALK_CU_PU_DATA, final_data)
        return sent

    def cmd_talk_start(self):
        pkt = { 
            "Name" : "OPTalk", 
            "OPTalk" : { 
                "Action" : "Start", 
                "AudioFormat" : { 
                    "BitRate" : 128, 
                    "EncodeType" : "G711_ALAW", 
                    "SampleBit" : 8, 
                    "SampleRate" : 8000 
                }
            }
        }

        response = self._generic_command(xmconst.TALK_REQ, pkt)
        return response

    def cmd_talk_stop(self):
        pkt = { 
            "Name" : "OPTalk", 
            "OPTalk" : { 
                "Action" : "Stop", 
                "AudioFormat" : { 
                    "BitRate" : 128, 
                    "EncodeType" : "G711_ALAW", 
                    "SampleBit" : 8, 
                    "SampleRate" : 8000 
                }
            }
        }

        response = self._generic_command(xmconst.TALK_REQ, pkt)
        return response

    @staticmethod
    def talk_convert_to_pcm(src,
        volume=1.0, 
        app='/usr/bin/ffmpeg', 
        args=(
            '-y', 
            '-f', 'alaw',
            '-ar', '8000',
            '-ac', '1',
            )):

        if not os.path.exists(app):
            return (False, None)

        if not os.path.exists(src):
            return (False, None)
        
        dst_final = src + '.pcm'

        fullargs = [app]
        fullargs.append('-loglevel')
        fullargs.append('panic')
        fullargs.append('-i')
        fullargs.append(src)
        [fullargs.append(a) for a in args]

        if volume != 1.0:
            fullargs.append('-filter:a')
            fullargs.append('volume={}'.format(volume))

        fullargs.append(dst_final)

        child = subprocess.Popen(fullargs)
        child.communicate()

        return (child.returncode == 0, dst_final) # True if 0

    @staticmethod
    def talk_get_chunks(pcmfile):
        retdata = None
        try:
            pcmdata = open(pcmfile, 'rb').read()
            data = [pcmdata[i:i+320] for i in range(0, len(pcmdata), 320)]
            retdata = data
        except:
            print('Got an exception on talk_get_chunks')

        return retdata
