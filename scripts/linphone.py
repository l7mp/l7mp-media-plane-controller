import subprocess
import time
import pyshark
import argparse
import shlex

def start(executable_file):
    return subprocess.Popen(
        executable_file,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        bufsize=1,
        universal_newlines=True
    )

def read(process):
    return process.stdout.readlines().strip()

def write(process, message):
    process.stdin.write(f"{message.strip()}\n")
    # process.stdin.flush()


def terminate(process):
    process.stdin.close()
    process.terminate()
    process.wait(timeout=0.2)

if __name__ == '__main__':
    t = time.localtime()
    parser = argparse.ArgumentParser(description='Linphone automatization and rtcp capture')
    parser.add_argument('--play-file', '-p', type=str, dest='play_file',
                        help='Location of wav file to play.')
    parser.add_argument('--record-file', '-r', type=str, dest='record_file',
                        help='Location of record file to save.')
    parser.add_argument('--command', '-c', type=str, dest='command',
                        help='Command to Linphone (call 456 or answer 1)')
    args = parser.parse_args()

    process = None
    tshark_process = None

    try:
        t_command = shlex.split('tshark -i any -f "udp" -w traffic.pcap')
        tshark_process = start(t_command)
        process = start('linphonec')
        time.sleep(1)
        write(process, 'soundcard use files')
        time.sleep(1)
        write(process, f'play {args.play_file}')
        time.sleep(1)
        write(process, f'record {args.record_file}')

        time.sleep(10)
        write(process, args.command)

        capture = pyshark.LiveCapture(interface='any', display_filter='rtcp')
        for p in capture.sniff_continuously(packet_count=20):
            try:
                current_time = time.strftime("%H:%M:%S", t)
                moslq = p[7]._all_fields["rtcp.xr.voipmetrics.moslq"]
                moscq = p[7]._all_fields["rtcp.xr.voipmetrics.moscq"]
                rfactor = p[7]._all_fields["rtcp.xr.voipmetrics.rfactor"]
                rtdelay = p[7]._all_fields["rtcp.xr.voipmetrics.rtdelay"]
                meanjitter = p[6]._all_fields["rtcp.xr.stats.meanjitter"]
                packet_count = p[3]._all_fields["rtcp.sender.packetcount"]
                print(f'{current_time}\tMOS-LQ: {moslq}\tMOS-CQ: {moscq}\t'
                    f'R-Factor: {rfactor}\tRound Trip Delay: {rtdelay}ms\t'
                    f'Mean Jitter: {meanjitter}ms\tPacket Count: {packet_count}')
            except:
                continue
        write(process, 'quit')
        time.sleep(1)
        terminate(process)
        terminate(tshark_process)
    except KeyboardInterrupt or AttributeError:
        write(process, 'quit')
        time.sleep(1)
        terminate(process)
        terminate(tshark_process)
    except:
        print("call ended")