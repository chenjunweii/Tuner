import sys
sys.path[0] += '/../'

import os
import tvm
import cv2
import nnvm
import zipfile
import numpy as np
from mxnet import nd
from tvm import autotvm
from nnvm import compiler
from nnvm.frontend import from_mxnet
from tvm.contrib import graph_runtime
from mxnet.model import load_checkpoint
from tool.load_deploy_model import * # import load_deploy_model # import save_tvm_params, save_tvm_graph
from utils import *
from time import time
import argparse

parser = argparse.ArgumentParser(description = '')
 
parser.add_argument('--network', type = str, default = None, help = 'Network Architecture')

parser.add_argument('--target', type = str, default = 'cuda', help = 'Deploy Target')

parser.add_argument('--board', type = str, help = 'board')

parser.add_argument('--dtype', type = str, default = 'float32', help = 'Data Type')

parser.add_argument('--tuner', type = str, default = 'xgb', help = 'Select Tuner')

parser.add_argument('--recompile', action = 'store_true', help = 'ReCompile')

parser.add_argument('--local', action = 'store_true', help = 'ReCompile')

parser.add_argument('--remote', action = 'store_true', help = 'ReCompile')

parser.add_argument('--device', type = str, help = 'Select Tuner')

parser.add_argument('--size', type = int, help = 'Select Tuner')

parser.add_argument('--lib', type = str, help = 'TVM')

args = parser.parse_args()

target_host = None

if args.target == 'cuda':
    target = 'cuda'
elif args.target == 'llvm':
    target = 'llvm'
else:
    print('[!] Not Supported Yet')

if args.board == 'tx2':
    if args.device == 'cpu':
        target = 'llvm'
    elif args.device == 'gpu':
        target = 'cuda -libs=cudnn' if args.lib == 'cudnn' else 'cuda'
    target_host = 'llvm -target=aarch64-linux-gnu'
    device_key = 'tx2'

ctx = tvm.gpu(0)

shapes = (1, args.size, args.size, 3)

net, params = load_mxnet_model('deploy_ssd_mobilenet_v2_680-det', 240, 'model')

r, g, b = 123, 117, 104 

params['mean'] = nd.array(np.array([r, g, b]).reshape([1, 3, 1, 1]))

net, params = nnvm.frontend.from_mxnet(net, params)

inputs = np.ones(shapes)

out = 'ssd_{}_{}'.format(args.network, args.size)

print("[*] Compile...")

if args.lib == 'cudnn':
    with compiler.build_config(opt_level = 3):
        graph, lib, params = compiler.build(net, target, {"data": shapes, "mean" : (1, 3, 1, 1)}, params = params)
else:

    log = os.path.join('log', '{}.log'.format(out))
    if not os.path.isfile(log):
        print('[!] Warning {} is not exist'.format)
        with autotvm.apply_history_best(log):
            with compiler.build_config(opt_level = 3):
                graph, lib, params = compiler.build(net, target, {"data": shapes, "mean" : (1, 3, 1, 1)}, params = params)
    else:
        with compiler.build_config(opt_level = 3):
            graph, lib, params = compiler.build(net, target, {"data": shapes, "mean" : (1, 3, 1, 1)}, params = params)

lib.export_library('so/{}.tvm.so'.format(out))

print('[*] Model is Compiled')

m = graph_runtime.create(graph, lib, ctx)

save_tvm_params('params/{}'.format(out), params)

save_tvm_graph('graph/{}'.format(out), graph)

print('[*] Graph RunTime is Created')

m.set_input('data', tvm.nd.array(inputs.astype(np.float32))) # astype

m.set_input(**params)

print('[*] Run ')

total = 0

inputs = inputs.astype(np.float32)

ndinputs = tvm.nd.array(inputs)

m.set_input('data', ndinputs)

for i in range(10):

    #ndinputs
    #start = time()
    #e = time() - start
    #total += e
    #print('set input : ', e)
    start = time()
    m.run()
    e = time() - start
    total += e
    print('Forward : ', e)

    start = time()
    cls_prob = m.get_output(0).asnumpy()
    e = time() - start
    total += e
    print('get class prob : ', e)

    start = time()
    loc_preds = m.get_output(1).asnumpy()
    e = time() - start
    total += e
    print('get loc preds : ', e)

    start = time()
    
    anchor_boxes = m.get_output(2).asnumpy()
    
    e = time() - start
    
    total += e

    print('get anchor_boxes : ', e)

    print('Total : ', total)

    print('anchor sum : ', anchor_boxes.sum())
    
    print('=========================')

    total = 0

print(cls_prob.asnumpy().shape)
print(loc_preds.asnumpy().shape)
print(loc_preds.asnumpy().shape)




