import subprocess
import time
import pyshark
import argparse
import shlex
from prometheus_client import start_http_server, Gauge

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

def prometheus(param):
    address, port = param.split(":")
    start_http_server(int(port), address)

    mos_lq_gauge = Gauge('mos_lq', 'Mean Opinion Score Listen Quality')
    mos_cq_gauge = Gauge('mos_cq', 'Mean Opinion Score Conversation Quality')
    r_factor_gauge = Gauge('r_factor', 'Overall call quality metric')
    rt_delay_gauge = Gauge('round_trip_delay', 'Round Trip Delay')
    mean_jitter_gauge = Gauge('mean_jitter', 'Meand Jitter')
    packet_count_gauge = Gauge('packet_count', 'Packet Count')

    return mos_lq_gauge, mos_cq_gauge, r_factor_gauge, rt_delay_gauge, mean_jitter_gauge, packet_count_gauge

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Linphone automatization and rtcp capture')
    parser.add_argument('--play-file', '-p', type=str, dest='play_file',
                        help='Location of wav file to play.')
    parser.add_argument('--record-file', '-r', type=str, dest='record_file',
                        help='Location of record file to save.')
    parser.add_argument('--command', '-c', type=str, dest='command',
                        help='Command to Linphone (call 456 or answer 1)')
    parser.add_argument('--prometheus', '-pr', type=str, dest='prometheus',
                        help='Prometheus server address. eg. 127.0.0.1:8000')
    args = parser.parse_args()

    process, tshark_process = None, None
    mos_lq_gauge, mos_cq_gauge, r_factor_gauge, rt_delay_gauge, mean_jitter_gauge, packet_count = (None,)*6

    try:
        if args.prometheus: 
            mos_lq_gauge, mos_cq_gauge, r_factor_gauge, rt_delay_gauge, mean_jitter_gauge, packet_count_gauge = prometheus(args.prometheus)

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
        for p in capture.sniff_continuously(packet_count=50):
            current_time = time.strftime("%H:%M:%S", time.localtime())
            moslq = p[7]._all_fields["rtcp.xr.voipmetrics.moslq"]
            moscq = p[7]._all_fields["rtcp.xr.voipmetrics.moscq"]
            rfactor = p[7]._all_fields["rtcp.xr.voipmetrics.rfactor"]
            rtdelay = p[7]._all_fields["rtcp.xr.voipmetrics.rtdelay"]
            meanjitter = p[6]._all_fields["rtcp.xr.stats.meanjitter"]
            packet_count = p[3]._all_fields["rtcp.sender.packetcount"]

            if args.prometheus:
                if moslq != '127': mos_lq_gauge.set(float(moslq))
                if moscq != '127': mos_cq_gauge.set(float(moscq))
                if rfactor != '127': r_factor_gauge.set(int(rfactor))
                if rtdelay != '0': rt_delay_gauge.set(int(rtdelay))
                if meanjitter != '0': mean_jitter_gauge.set(float(meanjitter))
                if packet_count != '0': packet_count_gauge.set(int(packet_count)) 

            print(f'{current_time}\tMOS-LQ: {moslq}\tMOS-CQ: {moscq}\t'
                f'R-Factor: {rfactor}\tRound Trip Delay: {rtdelay} ms\t'
                f'Mean Jitter: {meanjitter} ms\tPacket Count: {packet_count}')
        write(process, 'quit')
        time.sleep(1)
        terminate(process)
        terminate(tshark_process)
    except KeyboardInterrupt or AttributeError:
        write(process, 'quit')
        time.sleep(1)
        terminate(process)
        terminate(tshark_process)