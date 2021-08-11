import numpy as np
import pandas as pd
import glob
import matplotlib.pyplot as plt
import matplotlib.cbook as cbook
import argparse
import re

COLUMNS = ['MOS-LQ', 'MOS-CQ', 'R-FACTOR', 'RTT', 'MEAN-JITTER']

# https://stackoverflow.com/a/5967539/12243497
def atof(text):
    try:
        retval = float(text)
    except ValueError:
        retval = text
    return retval

def natural_keys(text):
    '''
    alist.sort(key=natural_keys) sorts in human order
    http://nedbatchelder.com/blog/200712/human_sorting.html
    (See Toothy's implementation in the comments)
    float regex comes from https://stackoverflow.com/a/12643073/190597
    '''
    return [ atof(c) for c in re.split(r'[+-]?([0-9]+(?:[.][0-9]*)?|[.][0-9]+)', text) ]


parser = argparse.ArgumentParser(description='Boxplot maker')
parser.add_argument('--dir', '-d', type=str, dest='dir', help='Directory which contains subdirectories with the measured data')
parser.add_argument('--output', '-o', type=str, dest='output', help='Output location of the created figures',
                    default="")
parser.add_argument('--title', '-t', type=str, dest='title', help='Title of the charts')
args = parser.parse_args()


files = glob.glob(f"{args.dir}/**/*.csv", recursive=True)
files.sort(key=natural_keys)
labels = [f.split("/")[-2] for f in files] # Subdirectory name will be the labels on each block 
dfList = [pd.read_csv(f) for f in files]

mos_lq_stats = {}
mos_cq_stats = {}
r_factor_stats = {}
rtt_stats = {}
mean_jitter_stats = {}

stats = {
    'MOS-LQ': {},
    'MOS-CQ': {},
    'R-FACTOR': {},
    'RTT': {},
    'MEAN-JITTER': {}
}
for label, df in zip(labels, dfList):
    for c in COLUMNS:
        arr = df[c].tolist()
        arr = [float(i.replace(',', '.')) if isinstance(i, str) else float(i) for i in arr]
        arr = [elem for elem in arr if elem <= 1000 and elem != 127 and elem != 0]

        stats[c][label] = cbook.boxplot_stats(arr)[0]
        stats[c][label]['label'] = label
        stats[c][label]['q1'], stats[c][label]['q3'] = np.percentile(arr, [25, 75])

for c in COLUMNS:
    fig = plt.figure()
    ax = fig.add_subplot()
    if c in ['RTT', 'MEAN-JITTER']:
        ax.set_ylabel(c + ' (ms)')
    else:
        ax.set_ylabel(c)
    ax.set_xlabel('# background call')
    ax.bxp([stats[c][i] for i in labels])
    ax.set_title(args.title)
    ax.yaxis.grid()
    out = f'{c}.jpg' if args.output == '' else args.output + f'/{c}.jpg' 
    fig.savefig(out)
    plt.close()