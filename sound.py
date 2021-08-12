#!/usr/bin/python3

# Call scripty with:
# ./sound.py CAM_IP FILENAME

import sys
import os

from xmcam import *
from xmconst import *
from time import sleep

CAM_IP = sys.argv[1]
FILE = sys.argv[2]

CAM_PORT = 34567

if __name__ == '__main__':

    cam = XMCam(CAM_IP, CAM_PORT, 'admin', '')
    login = cam.cmd_login()
    print(login)

    sleep(0.1)

    streamconn = cam.create_sub_connection(True)

    sleep(0.1)
    
    success, pcm_audio_path = XMCam.talk_convert_to_pcm(FILE)

    if success: # if audio converted into PCM successfully

        streamconn.cmd_talk_claim()
        print("CLAIM")
        
        sleep(0.1)

        cam.cmd_talk_start()
        print("START")
        
        audio_chunks = XMCam.talk_get_chunks(pcm_audio_path)

        if audio_chunks is not None:

            for audio_chunk in audio_chunks:
                streamconn.cmd_talk_send_stream(audio_chunk)

            # Sufficient wait for playing whole file
            stat = os.stat(pcm_audio_path).st_size
            sleep(stat / 8000)

        sleep(0.05)

        cam.cmd_talk_stop()
        print("END")
        
        sleep(0.1)

    sleep(0.1)

    cam.disconnect()
    print("END")
