import torch
import torch.nn.functional as F
from torchvision import models
import numpy as np
import cv2
import os, sys
from torchsummary import summary
#from classes_label import labels as classes

######## config #############
test_images_path = sys.argv[1]
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

os.environ['CUDA_VISIBLE_DEVICES'] = ",".join(f"{id}" for id in cards_id)


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

