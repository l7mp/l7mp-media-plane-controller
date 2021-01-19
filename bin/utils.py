import random
import string
import bencodepy
import socket
import subprocess

# Set up the bancode library
bc = bencodepy.Bencode(
    encoding='utf-8'
)

# Generate a random string for cookie 
def gen_cookie(length):
    return ''.join(random.choice(string.ascii_lowercase) for i in range(length))

# Send traffic to rtpengine
def send(args, file, bind_address, bind_port):
    # Open UDP4 socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((bind_address, bind_port))
    server_address = (args.addr, args.port)

    # Generate ng message
    cookie = gen_cookie(5)
    data = bencodepy.encode(file).decode() # Here goes all of the data, decode needed to remove b'

    # The ng protcol has two parts a cookie for responses and others and a
    # bencode dictinory which contain the data
    message = str(cookie) + " " + str(data)
    sent = sock.sendto(message.encode('utf-8'), server_address)

    data, server = sock.recvfrom(4096)
    data = data.decode()
    data = data.split(" ", 1)

    result = bc.decode(data[1])
    sock.close()
    
    return result


# Run a certain number of ffmpeg command 
def ffmpeg(args, cnt, offer_rtp_address, answer_rtp_address):
    procs = []
    # Start an offer and an answer ffmpeg stream. 
    for c in range(cnt):
        procs.append(subprocess.Popen(["ffmpeg", "-re", "-i", args.audio_file, "-ar", "8000", "-ac", "1", "-acodec", "pcm_mulaw", "-f", "rtp", offer_rtp_address[c]]))
        procs.append(subprocess.Popen(["ffmpeg", "-re", "-i", args.audio_file, "-ar", "8000", "-ac", "1", "-acodec", "pcm_mulaw", "-f", "rtp", answer_rtp_address[c]]))
    # If everyhing is done close the processes
    for proc in procs:
        proc.communicate()

# Run tcpdump in the background on a given interface
# def tcpdump():
#     return subprocess.Popen(["sudo", "tcpdump", "-i", args.tcpdump, "udp", "-vvn", "-w", "traffic.pcap"])