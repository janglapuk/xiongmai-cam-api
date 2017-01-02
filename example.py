from xmcam import *
from xmconst import *
from time import sleep

CAM_IP = '192.168.1.10'
CAM_PORT = 34567

if __name__ == '__main__':
    xm = XMCam(CAM_IP, CAM_PORT, 'admin', 'admin')
    login = xm.cmd_login()
    print(login)

    print(xm.cmd_system_function())
    print(xm.cmd_system_info())
    print(xm.cmd_channel_title())
    print(xm.cmd_OEM_info())
    print(xm.cmd_storage_info())
    print(xm.cmd_users())

    print(xm.cmd_ptz_control(PTZ_LEFT))
    sleep(1)
    print(xm.cmd_ptz_control(PTZ_LEFT, True))

    cfg = xm.cmd_config_export('export.cfg')
    print('Config ==>', cfg)

    snap = xm.cmd_snap('test.jpg')
    print('SNAP ==>', snap)
