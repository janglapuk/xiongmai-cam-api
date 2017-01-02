import socket
import xmconst
import json
import os
from struct import pack, unpack
from pprint import pprint, pformat


class XMCam:
    socket = None
    sid = 0
    sequence = 0

    ip = ''
    port = 0
    username = password = ''

    def __init__(self, ip, port, username, password):
        self.ip = ip
        self.port = port
        self.username = username
        self.password = password
        self.connect()

    def __del__(self):
        self.disconnect()

    def prettify(self, json_data):
        data_dict = json.loads(json_data)
        return pformat(data_dict)

    def unpack_data(self, data, is_bytearray=True):
        if is_bytearray:
            parsed = list(bytearray(data.encode('ascii')))
        else:
            parsed = [c.encode('hex') for c in data]
        return parsed

    def prepare_generic_command_head(self, msgid, params):
        pkt = params

        if msgid != xmconst.LOGIN_REQ2:
            params['SessionID'] = self.build_packet_sid()

        cmd_data = self.build_packet(msgid, pkt)

        self.socket.send(cmd_data)

        reply_head = self.get_reply_head()

        return reply_head

    def prepare_generic_command(self, msgid, params):
        reply_head = self.prepare_generic_command_head(msgid, params)

        out = self.get_reply_data(reply_head)

        if msgid == xmconst.LOGIN_REQ2 and 'SessionID' in reply_head:
            #self.sid = int(reply_head['SessionID'], 16)
            self.sid = reply_head['SessionID']

        if out:
            return json.dumps(out)

        return None

    def prepare_generic_command_download(self, msgid, params, file):
        reply_head = self.prepare_generic_command_head(msgid, params)
        out = self.get_reply_data(reply_head)

        if out:
            with open(file, 'wb') as f:
                f.write(out)

            return True

        return False

    def get_reply_head(self):
        data = self.socket.recv(4)
        head_flag, version, _, _ = unpack('BBBB', data)

        data = self.socket.recv(8)
        sid, seq = unpack('ii', data)

        data = self.socket.recv(8)
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

    def get_reply_data(self, reply_head):
        reply = reply_head
        length = reply['Content_Length']
        out = ''

        for i in range(0, length):
            data = self.socket.recv(1)
            out += data

        return out

    def build_packet_sid(self):
        return '0x%08x' % self.sid

    def build_packet(self, type, params):
        pkt_type = type
        pkt_prefix_1 = (0xff, 0x01, 0x00, 0x00)
        pkt_prefix_2 = (0x00, 0x00, 0x00, 0x00)

        '''
        my $msgid = pack('s', 0) . pack('s', $pkt_type);
        my $pkt_prefix_data =  pack('c*', @pkt_prefix_1) . pack('i', $self->{sid}) . pack('c*', @pkt_prefix_2). $msgid;
        '''

        header = pack('B'*len(pkt_prefix_1), *pkt_prefix_1)
        header += pack('I', self.sid)
        header += pack('B'*len(pkt_prefix_2), *pkt_prefix_2)
        header += pack('H', 0) + pack('H', pkt_type)

        pkt_params_data = json.dumps(params) #+ '\n'
        pkt_data = header + pack('I', len(pkt_params_data)) + bytes(pkt_params_data.encode('ascii'))

        #print(':'.join(x.encode('hex') for x in pkt_data))
        return pkt_data

    def connect(self):
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.ip, self.port))
        except Exception as e:
            print(e)
            return False

        return True

    def disconnect(self):
        self.socket.close()

    def cmd_login(self):
        pkt = {
            'EncryptType': 'MD5',
            'LoginType': 'DVRIP-Web',
            'PassWord': self.password,
            'UserName': self.username
        }

        reply_json = self.prepare_generic_command(xmconst.LOGIN_REQ2, pkt)

        return self.prettify(reply_json)

    def cmd_system_function(self):
        pkt = {
            'Name': 'SystemFunction'
        }

        reply_json = self.prepare_generic_command(xmconst.ABILITY_GET, pkt)
        return self.prettify(reply_json)

    def cmd_system_info(self):
        pkt = {
            'Name': 'SystemInfo'
        }

        reply_json = self.prepare_generic_command(xmconst.SYSINFO_REQ, pkt)
        return self.prettify(reply_json)

    def cmd_keep_alive(self):
        pkt = {
            'Name': 'KeepAlive'
        }

        return self.prepare_generic_command(xmconst.KEEPALIVE_REQ, pkt)

    def cmd_channel_title(self):
        pkt = {
            'Name': 'ChannelTitle'
        }

        reply_json = self.prepare_generic_command(xmconst.CONFIG_CHANNELTILE_GET, pkt)
        return self.prettify(reply_json)

    def cmd_OEM_info(self):
        pkt = {
            'Name': 'OEMInfo'
        }

        reply_json = self.prepare_generic_command(xmconst.SYSINFO_REQ, pkt)
        return self.prettify(reply_json)

    def cmd_storage_info(self):
        pkt = {
            'Name': 'StorageInfo'
        }

        reply_json = self.prepare_generic_command(xmconst.SYSINFO_REQ, pkt)
        return self.prettify(reply_json)


    def cmd_users(self):
        pkt = {

        }

        reply_json = self.prepare_generic_command(xmconst.USERS_GET, pkt)
        return self.prettify(reply_json)

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

        reply_json = self.prepare_generic_command(xmconst.PTZ_REQ, pkt)
        return self.prettify(reply_json)

    def cmd_photo(self, file):
        pkt = {

        }

        reply = self.prepare_generic_command_download(xmconst.PHOTO_GET_REQ, pkt, file)
        return reply

    def cmd_config_export(self, file):
        pkt = {
            'Name': ''
        }

        reply = self.prepare_generic_command_download(xmconst.CONFIG_EXPORT_REQ, pkt, file)
        return reply

    # Just because no snap command supported, we need external program to capture from RTSP stream
    # using avconv or ffmpeg
    def cmd_external_avconv_snap(self, file, app='/usr/bin/avconv',
                                 rtsp='rtsp://192.168.1.10/user=admin&password=admin&channel=1&stream=0.sdp',
                                 args=('-y', '-f', 'image2', '-vframes', '1', '-pix_fmt', 'yuvj420p')):

        if not os.path.exists(app):
            return False

        import subprocess

        # Add executable
        fullargs = [app]

        # Append input arg
        fullargs.append('-i')
        fullargs.append(rtsp)

        # Append other args
        [fullargs.append(a) for a in args]

        # Lastly, append output arg
        fullargs.append(file)

        # child = subprocess.Popen(process, stdout=subprocess.PIPE)
        child = subprocess.Popen(fullargs)
        child.communicate()

        return child.returncode == 0 # True if 0

    def cmd_snap(self, file):
        retval = self.cmd_external_avconv_snap(file)
        return retval
