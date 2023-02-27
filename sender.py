#!/usr/bin/python3

"""
Only python package required is pyserial:

    pip install pyserial

Use this wee script to send a command queue to a Polargraph machine.

If the filename is "mycommandqueue.txt" and the machine is connected on COM7, then do:

    python send.py mycommandqueue.txt COM7
    
    
"""


import os
import serial
import time
from datetime import timedelta
import argparse
import csv

import sys

BAUD_RATE = 57600


class Polargraph():
    """
    This is a crude model of a drawing machine. It includes it's drawing state
    as well as the state of the communications lines to the machine and the
    queue of commands going to it.
    """
    serial_port = None
    file = None
    log_mode = None

    # State
    ready = False
    file_position = 0
    total_lines = 0

    #LOGGING CONFIG
    log_header= ['line', 'command', 'total_lines', 'percent', 'response', 'commands_ran', 'tim_ran', 'time_per_command', 'time_left', 'hours_left', 'minutes_left', 'seconds_left']


    def __init__(self, dry_run=False, log_mode=None, log_target=None):
        self.time_started = time.time()
        self.dry_run = dry_run
        self.log_mode = log_mode
        self.log_target = log_target

    def init_logger(self):
        if self.log_mode == 'file':
            self.log_file = open(self.log_target, 'w')
        elif self.log_mode == 'console':
            self.log_file = sys.stdout
        else:
            self.log_file = None

        if self.log_file:
            self.log_writer = csv.DictWriter(self.log_file, fieldnames=self.log_header)
            self.log_writer.writeheader()


    def close_logger(self):
        if self.log_file:
            self.log_file.close()

    
    def start_serial_comms(self, comm_port, baud_rate=57600):
        """
        Attempts to connect this machine to it's comm_port. It starts two
        threads, one for reading that is attached to the 'received_log'
        list, and one thread for writing that is attached to the main outgoing
        command queue.

        :param comm_port: The name of the comm port
        :param baud_rate: The speed to open the serial connection at

        :return:
        """

        if self.dry_run:
            return True


        try:
            self.serial_port = serial.Serial(comm_port, baudrate=baud_rate)
            print ("Connected successfully to %s (%s)." % (comm_port, serial))
            return True

        except Exception as e:
            self.serial_port = None
            return False

    def load_file(self, filename):
        """
        Checks that the file exists, opens it and counts the lines in it.

        :param filename:
        :return:
        """

        if os.path.isfile(filename):
            print ("Found %s!" % os.path.abspath(filename))
            self.file = open(filename, 'r')

            # Lets have a quick review of this file
            lines = 0
            for lines, l in enumerate(self.file):
                pass
            self.total_lines = lines + 1
            print ("This file has %s lines." % self.total_lines)

            # reset the file position
            self.file.seek(0)
        else:
            raise Exception("File %s not found!" % filename)


    def read_line(self):
        if self.dry_run:
            l = "READY -- DRY RUN"
        else:
            l = self.serial_port.readline().decode('ascii')
            l.strip()
        
        time_ran = 0
        time_per_command = 0
        time_projected = 0
        time_left = 0

        
        if l.startswith("READY"):
            # if it's changing from not ready to ready, then it's just finished a command
            if not self.ready:
                time_ran = time.time() - self.time_started
                time_per_command = time_ran / (self.file_position + 1)
                time_projected = self.total_lines * time_per_command
                time_left = timedelta(time_projected - time_ran) if self.file_position < self.total_lines else timedelta(0)
                
        self.ready = True
        
        
        return {
            'response': l,
            'commands_ran': self.file_position,
            'tim_ran': time_ran,
            'time_per_command': time_per_command,
            'time_left': time_left ,
            'hours_left': int(time_left.seconds / 3600) if time_left else 0,
            'minutes_left': int((time_left.seconds % 3600) / 60) if time_left else 0,
            'seconds_left': int(time_left.seconds % 60) if time_left else 0,
        }

    def write_line(self):
        if self.ready and self.file:
            l = self.file.readline().strip()
            self.file_position += 1
            if not self.dry_run:
                self.serial_port.write((l + "\n").encode())
            self.ready = False
            return {
                'command': l,
                'line': self.file_position,
                'total_lines': self.total_lines,
                'percent': (float(self.file_position) / float(self.total_lines))
            }
        else:
            raise Exception("Not ready to write!")

    def commands_queued(self):
        return self.total_lines - self.file_position

    def close(self):
        #print ("Finished sending {:d} commands in {:0.2f}".format(self.total_lines, time.time() - self.time_started))
        self.file.close()
        self.close_logger()
        if self.serial_port:
            self.serial_port.close()
            

    def send_queue(self, input_file, comm_port):
        """
        This is the main loop that processes the command queue. It reads the
        next command, sends it to the machine, and then waits for a response
        before sending the next command.

        :return:
        """
        opened = self.start_serial_comms(comm_port=comm_port)
        if not opened:
            print("There was a problem opening the communications port. It should be entered exactly as you see it in" \
                  "your operating system.")
            exit(1)

        self.load_file(input_file)
        
        self.init_logger()

        self.ready = True
        while self.commands_queued():
            command_data = self.write_line()
            response_data = self.read_line()

            command_data.update(response_data)
            if self.log_file:
                self.log_writer.writerow(command_data)

        self.close()

def main(input_file, comm_port, dry_run=False, log_mode="console", log_target=None):    
    """
    """
    polargraph = Polargraph(dry_run=dry_run, log_mode=log_mode, log_target=log_target)
    polargraph.send_queue(input_file, comm_port)
    
    

if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument("command_queue", help="The name of the command queue file to send to the machine.")
    parser.add_argument("port", help="The name of the serial port to connect to the machine.")
    parser.add_argument("--dry-run", help="Simulate commands sending", action="store_true")
    parser.add_argument("--log-mode", help="log mode", default="console")
    parser.add_argument("--log-target", help="log target")
    #todo: add log argument
    #todo: add redis queue name argument


    args = parser.parse_args()
    main(
        args.command_queue,
        args.port,
        dry_run=args.dry_run,
        log_mode=args.log_mode,
        log_target=args.log_target
    )
    
 