#!/usr/bin/env python
# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# A simple native messaging host. Shows a Tkinter dialog with incoming messages
# that also allows to send message back to the webapp.

import struct
import sys
import json
import subprocess
import threading
import os


# On Windows, the default I/O mode is O_TEXT. Set this to O_BINARY
# to avoid unwanted modifications of the input/output streams.
if sys.platform == "win32":
    import os
    import msvcrt

    msvcrt.setmode(sys.stdin.fileno(), os.O_BINARY)
    msvcrt.setmode(sys.stdout.fileno(), os.O_BINARY)


# Helper function that sends a message to the chrome extension.
def send_message(message):
    # Write message size.
    sys.stdout.write(struct.pack('I', len(message)))
    # Write the message itself.
    sys.stdout.write(message)
    sys.stdout.flush()


def error(error_message):
    send_message(json.dumps(["ERROR", error_message]))




_zeronet_process = None
_zeronet_stdout_reader = None
_zeronet_stderr_reader = None

_whereis_zeronet = ""
_whereis_zeronet_py = ""


class StreamReader:
    def __init__(self, stream):
        self.stream = stream
        self.buffer = ""
        self.lock = threading.Lock()
        self.running = True

        def _thread_func():
            while self.running:
                line = self.stream.readline()
                self.lock.acquire()
                self.buffer += line
                self.lock.release()

        self.thread = threading.Thread(target=_thread_func)
        self.thread.start()

    def flush(self):
        self.lock.acquire()
        ret = self.buffer
        self.buffer = ""
        self.lock.release()
        return ret


    def read(self):
        self.lock.acquire()
        ret = self.buffer
        self.lock.release()
        return ret

    def stop(self):
        self.running = False


class Interface(object):
    @staticmethod
    def ping(message):
        if 'message' in message and message['message'] == 'Magic mirror in my hand, who is the fairest in the land?':
            return ['ping', 'My Queen, you are the fairest in the land.']
        else:
            return ['ping', 'My Queen, you are the fairest here so true. But Snow White is a thousand times more beautiful than you.']

    @staticmethod
    def start(message):
        """ Starts a zeronet instance, while storing its output."""
        global _zeronet_process, _zeronet_stdout_reader, _zeronet_stderr_reader
        if _whereis_zeronet is None or _whereis_zeronet_py is None:
            return ["start", "Must specifiy zeronet directory."]
        elif not os.path.isdir(_whereis_zeronet):
            return ["start", "Must specify valid zeronet directory ('%s' does not exist)" % _whereis_zeronet]
        elif not os.path.isfile(_whereis_zeronet_py):
            return ["start", "Must specify valid location of zeronet.py ('%s' does not exist)" % _whereis_zeronet_py]
        if _zeronet_process is not None:
            return ["start", "redundant"]
        _zeronet_process = subprocess.Popen(["env", "python", _whereis_zeronet_py], cwd=_whereis_zeronet, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
        _zeronet_stdout_reader = StreamReader(_zeronet_process.stdout)
        _zeronet_stderr_reader = StreamReader(_zeronet_process.stderr)
        return ["start", "success"]

    @staticmethod
    def stop(message):
        """ Stops a running zeronet instance, if any."""
        global _zeronet_process, _zeronet_stdout_reader, _zeronet_stderr_reader
        if _zeronet_process is None:
            return ["stop", "notrunning"]
        else:
            _zeronet_process.kill()
            _zeronet_stdout_reader.stop()
            _zeronet_stderr_reader.stop()
            _zeronet_process = None
            _zeronet_stdout_reader = None
            _zeronet_stderr_reader = None
            return ["stop", "success"]

    @staticmethod
    def whereiszeronet(message):
        """ Specifies zeronet dir."""
        global _whereis_zeronet_py, _whereis_zeronet
        _whereis_zeronet = message[1]
        if not isinstance(_whereis_zeronet, str) and not isinstance(_whereis_zeronet, unicode):
            return ["ERROR", "Expected string."]
        _whereis_zeronet_py = os.path.join(_whereis_zeronet, "zeronet.py")

    @staticmethod
    def stdout(message):
        """ Returns the stdout so far."""
        global _zeronet_stdout_reader
        if _zeronet_stdout_reader is None:
            return ["ERROR", "Zeronet not running."]

        ret = _zeronet_stdout_reader.read()
        return ["stdout", ret]

    @staticmethod
    def stderr(message):
        """ Returns the stdout so far."""
        global _zeronet_stderr_reader
        if _zeronet_stderr_reader is None:
            return ["ERROR", "Zeronet not running."]
        ret = _zeronet_stderr_reader.read()
        return ["stdout", ret]


request_handlers = {key: value.__func__ for key, value in Interface.__dict__.items() if isinstance(value, staticmethod)}





# Loop that reads messages from the chrome extension.
def read_thread_loop():
    while True:
        # Read the message length (first 4 bytes).
        text_length_bytes = sys.stdin.read(4)

        if len(text_length_bytes) == 0:
            return

        # Unpack message length as 4 byte integer.
        text_length = struct.unpack('i', text_length_bytes)[0]

        # Read the text (JSON object) of the message.
        text = sys.stdin.read(text_length).decode('utf-8')
        msg = json.loads(text)

        # print(decoded_message)
        if not isinstance(msg, list):
            error('Expected list object as request.')
            continue
        request = msg[0]

        if not isinstance(request, str) and not isinstance(request, unicode):
            error('Expected first element of request to be a string.')
            continue

        # if VERBOSE:
        #     print("REQ: " + request)

        if request not in request_handlers:
            error("Unimplemented request, '%s'." % request)
            continue
        handler = request_handlers[request]

        reply = handler(msg)
        send_message(json.dumps(reply))


def main():
    # import pydevd
    # pydevd.settrace('localhost', port=12421, stdoutToServer=True, stderrToServer=True)
    read_thread_loop()
    # Interface.start(None)
    if _zeronet_process is not None:
        _zeronet_process.kill()
    sys.exit(0)


if __name__ == '__main__':
    main()
