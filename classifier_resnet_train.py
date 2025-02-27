from PIL.Image import fromarray
import torch
import torch.nn as nn
import torch.nn.functional as F
from torchvision import models
from subprocess import Popen, TimeoutExpired, PIPE, check_call, check_output
# import resnet as models
import numpy as np
import cv2
import os
import random
from torchsummary import summary
import torch.optim as optim
#from classes_label import labels as classes

######## config #############
# classes = ["mouse","sipeed_logo"]       #训练标签
dataset_path = "/content/v831_restnet18/data"
classes = os.listdir(dataset_path)
with open('/label.txt', mode='wt', encoding='utf-8') as myfile:
    myfile.write('\n'.join(classes))
val_split_from_data = 0.1 # 10%
batch_size = 4
learn_rate = 0.001
total_epoch = 100
eval_every_epoch = 5
save_every_epoch = 20
dataload_num_workers = 2
input_shape = (3, 224, 224)
cards_id = [5]                                    #显卡的使用ID号
param_save_path = '/content/v831_restnet18/out/classifier_{}.pth'

def load_data(path, class_id, shape):
    data = []
    exts = [".jpg", ".jpeg", ".png"]
    files = os.listdir(path)
    for name in files:
        if not os.path.splitext(name.lower())[1] in exts:
            continue
        img = cv2.imread(os.path.join(path, name))
        if type(img) == type(None):
            print("read file {} fail".format(os.path.join(path, name)))
            continue
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        img = cv2.resize(img, (shape[2], shape[1]))
        img = np.transpose(img, (2, 0, 1)).astype(np.float32) # hwc to chw layout
        img = (img - 127.5) * 0.0078125
        data.append((torch.from_numpy(img), class_id))
    return data

class Dataset:
    def __init__(self, data):
        self.data = data

    def __getitem__(self, i):
        return self.data[i]

    def __len__(self) -> int:
        return len(self.data)

if not os.path.exists("/content/v831_restnet18/out"):
    os.makedirs("/content/v831_restnet18/out")

device_s = ""
if torch.cuda.is_available():
    device_s = "cuda:0"
else:
    device_s = "cpu"
device = torch.device(device_s)
# device = torch.device("cuda:0" if

#device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
print(device)

trainset = []
valset = []

for i, label in enumerate(classes):
    path = os.path.join(dataset_path, label)
    print(path)
    data = load_data(path, i, input_shape)
    random.shuffle(data)
    val_len = int(val_split_from_data * len(data))
    trainset.extend(data[val_len:])
    valset.extend(data[:val_len])
random.shuffle(trainset)
random.shuffle(valset)



trainset = Dataset(trainset)
valset = Dataset(valset)
print("trainset len:{}, valset len:{}".format(len(trainset), len(valset)))


trainloader = torch.utils.data.DataLoader(trainset, batch_size=batch_size,
                                          shuffle=True, num_workers=dataload_num_workers)
valloader = torch.utils.data.DataLoader(valset, batch_size=batch_size,
                                         shuffle=False, num_workers=dataload_num_workers)


net = models.resnet18(pretrained=False, num_classes = len(classes))
net.to(device)

summary(net, input_size=input_shape)



criterion = nn.CrossEntropyLoss()
optimizer = optim.SGD(net.parameters(), lr=learn_rate, momentum=0.9)

print("start train ...")
for epoch in range(total_epoch):  # loop over the dataset multiple times

    running_loss = 0.0
    for i, data in enumerate(trainloader, 0):
        # get the inputs; data is a list of [inputs, labels]
        inputs, labels = data
        inputs = inputs.to(device)
        labels = labels.to(device)

        # zero the parameter gradients
        optimizer.zero_grad()

        # forward + backward + optimize
        outputs = net(inputs)
        loss = criterion(outputs, labels)
        loss.backward()
        optimizer.step()

        # print statistics
        running_loss += loss.item()
        if i % (len(trainloader)//2) == 0:
            print('[%d, %5d] loss: %.5f' %
                  (epoch, i, running_loss / (len(trainloader)//2)))
            running_loss = 0.0
    if (epoch + 1) % eval_every_epoch == 0:
        with torch.no_grad():
            running_loss = 0
            for i, data in enumerate(valloader, 0):
                inputs, labels = data
                inputs = inputs.to(device)
                labels = labels.to(device)
                outputs = net(inputs)
                loss = criterion(outputs, labels)
                running_loss += loss
            print("val loss: {:.5f}".format(running_loss / len(valloader)))
    if (epoch + 1) % save_every_epoch == 0:
        print("save model params to", param_save_path.format(epoch))
        torch.save(net.state_dict(), param_save_path.format(epoch))

print('Finished Training')

torch.save(net.state_dict(), param_save_path.format("final"))
# torch.save(net, "out/classifier.pt") # save Net object by pickle


import torch.onnx
import torch


batch_size = 4
x = torch.randn(batch_size, input_shape[0], input_shape[1], input_shape[2], requires_grad=False)
x = x.to(device)

torch.onnx._export(net, x, "/content/v831_restnet18/out/classifier.onnx", export_params=True)



#from classes_label import labels as classes

######## config #############
test_images_path = '/content/v831_restnet18/images' 
# classes = ("mouse","sipeed_logo")
dataset_path = "/content/v831_restnet18/data"
classes = os.listdir(dataset_path)
print(classes)
input_shape = (3, 224, 224)
cards_id = [0]                               #显卡的使用ID号
param_save_path = "/content/v831_restnet18/out/classifier_final.pth"
onnx_out_name = "/content/v831_restnet18/out/classifier.onnx"
ncnn_out_param = "/content/v831_restnet18/out/classifier.param"
ncnn_out_bin = "/content/v831_restnet18/out/classifier.bin"

#os.environ['CUDA_VISIBLE_DEVICES'] = ",".join(f"{id}" for id in cards_id)


def load_data(path, shape):
    data = []
    exts = [".jpg", ".jpeg", ".png"]
    files = os.listdir(path)
    files = sorted(files)
    for name in files:
        if not os.path.splitext(name.lower())[1] in exts:
            continue
        img = cv2.imread(os.path.join(path, name))
        if type(img) == type(None):
            print("read file {} fail".format(os.path.join(path, name)))
            continue
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        img = cv2.resize(img, (shape[2], shape[1]))
        img = np.transpose(img, (2, 0, 1)).astype(np.float32) # hwc to chw layout
        img = (img - 127.5) * 0.0078125
        data.append((torch.from_numpy(img), name))
    return data

class Dataset:
    def __init__(self, data):
        self.data = data

    def __getitem__(self, i):
        return self.data[i]

    def __len__(self) -> int:
        return len(self.data)


device_s = ""
if torch.cuda.is_available():
    device_s = "cuda:0"
else:
    device_s = "cpu"
device = torch.device(device_s)
# device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")

print(device)

testset = load_data(test_images_path, input_shape)

testset = Dataset(testset)


net = models.resnet18(pretrained=False, num_classes = len(classes))
net.to(device)
if device_s == "cpu":
    net.load_state_dict(torch.load(param_save_path,map_location='cpu'))
else:
    net.load_state_dict(torch.load(param_save_path))

# summary(net, input_size=input_shape)

with torch.no_grad():
    for i, data in enumerate(testset):
        input, name = data
        input = input.to(device)
        outputs = net(input.unsqueeze(0))
        result = F.softmax(outputs[0], dim=0)
        print("image: {}, raw output: {}, ".format(name, outputs[0]), end="")
        for i, label in enumerate(classes):
            print("{}: {:.3f}, ".format(label, result[i]), end="")
        print("")

print("export model")
from convert import torch_to_onnx, onnx_to_ncnn

if not os.path.exists("out"):
    os.makedirs("out")

with torch.no_grad():
    torch_to_onnx(net.to("cpu"), input_shape, out_name=onnx_out_name, device="cpu")
    onnx_to_ncnn(input_shape, onnx=onnx_out_name, ncnn_param=ncnn_out_param, ncnn_bin=ncnn_out_bin)


try:
  folder_path = '/images'
  shutil.rmtree(folder_path)
  print('Out Folder and its content removed')
except:
  print('Folder not deleted')
if not os.path.exists("/images"):
    os.makedirs("/images")
    
#cmd1 = ['rm', '/classifier.bin']
#cmd2 = ['rm', '/classifier.param']
cmd3 = ['cp','/content/v831_restnet18/out/classifier.bin','/']
cmd4 = ['cp','/content/v831_restnet18/out/classifier.param','/']
cmd5 = ['cp','-rf','/content/v831_restnet18/images','/']
cmd6 = ['zip', '-r', '/classifier.zip', '/images', '/classifier.bin', '/classifier.param']
#proc0 = check_output(cmd0)
#proc1 = check_output(cmd1)
#proc2 = check_output(cmd2)
proc3 = check_output(cmd3)
proc4 = check_output(cmd4)
proc5 = check_output(cmd5)
proc6 = check_output(cmd6)

print("###############################################")
print("##                DONE !!!!!                 ##")
print("###############################################")
