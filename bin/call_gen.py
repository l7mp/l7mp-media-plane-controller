from utils import send, ffmpeg
import sdp_transform
import time

# Generate an Answer Dict 
def generate_answer(args, call_id, label, from_tag, to_tag, port):
    data = {}
    data["ICE"] = "remove"
    data["call-id"] = str(call_id)
    data["command"] = "answer"
    data["from-tag"] = str(from_tag)
    data["label"] = str(label)
    data["sdp"] = "v=0\r\no=- 1607446271 1 IN IP4 " + args.sdpaddr + "\r\ns=tester\r\nt=0 0\r\nm=audio " + str(port) + " RTP/AVP 0\r\nc=IN IP4 " + args.sdpaddr + "\r\na=sendrecv\r\na=rtcp:" + str(port + 1)
    data["to-tag"] = str(to_tag)
    return data

# Generate an Offer Dict
def generate_offer(args, call_id, label, from_tag, port):
    data = {}
    data["ICE"] = "remove"
    data["call-id"] = str(call_id)
    data["command"] = "offer"
    data["from-tag"] = str(from_tag)
    data["label"] = str(label)
    data["sdp"] = "v=0\r\no=- 1607444729 1 IN IP4 " + args.sdpaddr + "\r\ns=tester\r\nt=0 0\r\nm=audio " + str(port) + " RTP/AVP 0\r\nc=IN IP4 " + args.sdpaddr + "\r\na=sendrecv\r\na=rtcp:" + str(port + 1)
    return data

# Start a certain number of calls.
# All calls have different ID and port pair
def generate_calls(args, cnt):
    start_port = 3000
    offers = []
    answers = []
    for _ in range(cnt):
        start_port += 2
        # Send an offer 
        offer = send(args, generate_offer(args, str(start_port) + "-" + str(start_port + 2), "caller" + str(start_port), 
            "from-tag" + str(start_port), start_port), 
            args.sdpaddr, start_port)
        start_port += 2
        # Send an answer
        answer = send(args, generate_answer(args, str(start_port - 2) + "-" + str(start_port), "callee" + str(start_port), 
            "from-tag" + str(start_port - 2), "to-tag" + str(start_port), start_port), 
            args.sdpaddr, start_port)
        # Parse the responses 
        parsed_offer = sdp_transform.parse(offer.get('sdp'))
        parsed_answer = sdp_transform.parse(answer.get('sdp'))
        # Get the generated ports
        offer_port = parsed_offer.get('media')[0].get('port')
        answer_port = parsed_answer.get('media')[0].get('port')
        # Generate addresses to send traffic to them 
        offers.append("rtp://" + args.addr + ":" + str(offer_port) + "?localrtpport=" + str(start_port - 2))
        answers.append("rtp://" + args.addr + ":" + str(answer_port) + "?localrtpport=" + str(start_port))
    # Wait a second to close every port what the for loop is opened 
    time.sleep(1)
    # Start the streams 
    ffmpeg(args, cnt, offers, answers)