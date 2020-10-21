import os
import time

import cv2
import numpy as np
import PIL
import torch
import torch.nn as nn
from torch.utils.data import DataLoader
import torchvision
from torchvision import transforms
from tqdm import tqdm

from dral.datasets import LabelledDataset
from dral.utils import get_resnet18_batch_transforms


def init_and_save(path):
    model = Model()
    model.save(path)


class Model:
    def __init__(self, model=None):
        self.device = torch.device(
            "cuda:0" if torch.cuda.is_available() else "cpu")
        print(f'CUDA: {self.device}')
        if model is None:
            model = torchvision.models.resnet18(pretrained=True)
            num_ftrs = model.fc.in_features
            model.fc = nn.Sequential(
                nn.Linear(num_ftrs, 256),
                nn.Linear(256, 2))
        self.model_conv = model.to(self.device)

        self.criterion = nn.CrossEntropyLoss()
        self.optimizer = torch.optim.Adam(
            self.model_conv.parameters(), lr=0.002, amsgrad=True)
        self.scheduler = torch.optim.lr_scheduler.MultiStepLR(
            self.optimizer, milestones=[100, 200, 300], gamma=0.5)

    def __call__(self, batch_x):
        return self.model_conv(batch_x)

    def predict(self, batch_x):
        with torch.no_grad():
            batch_x = batch_x.to(self.device)
            return self(batch_x)

    def predict_all(self, dataloader, batch_transforms=True):
        print('PREDICT ALL')
        if batch_transforms:
            transforms = get_resnet18_batch_transforms()
        transforms_time = 0
        feedforward_time = 0
        # predictions = np.empty((0, 2))
        predictions = torch.empty((0, 2), device=self.device)
        paths = []
        with torch.no_grad():
            for batch_x, img_paths in tqdm(dataloader):
                batch_x = batch_x.to(self.device)

                # start_transoform = time.time()
                # if batch_transforms:
                #     batch_x = transforms(batch_x)
                # transofrm_time = time.time() - start_transoform
                # transforms_time += transofrm_time

                start_pred = time.time()
                prediction = self(batch_x)
                feedforward_time += time.time() - start_pred
                start_transoform = time.time()
                predictions = torch.cat((predictions, prediction), 0)
                transforms_time += time.time() - start_transoform
                for path in img_paths:
                    paths.append(path)
        print(f"[DEBUG] loading time: {transforms_time}, feedforward time: {feedforward_time}")
        print(f'[DEBUG] Predictions shape: {predictions.shape}')
        
        return predictions.cpu().numpy(), paths

    def train(self, dataloader, epochs):
        self.model_conv.train()  # training mode
        itr = 1
        p_itr = 200
        total_loss = 0
        loss_list = []
        acc_list = []

        for epoch in range(epochs):
            for samples, labels in tqdm(dataloader):
                samples, labels = samples.to(self.device), \
                                  labels.to(self.device)
                self.optimizer.zero_grad()
                output = self.model_conv(samples)
                loss = self.criterion(output, labels)
                loss.backward()
                self.optimizer.step()
                total_loss += loss.item()
                self.scheduler.step()

                itr += 1
            pred = torch.argmax(output, dim=1)
            correct = pred.eq(labels)
            acc = torch.mean(correct.float())
            print('[Epoch {}/{}] Iteration {} -> Train Loss: {:.4f}, '
                  'Accuracy: {:.3f}'.format(
                        epoch+1, epochs, itr, total_loss/p_itr, acc))
            loss_list.append(total_loss/p_itr)
            acc_list.append(float(acc.cpu()))
            total_loss = 0

        return loss_list, acc_list

    def save(self, name):
        torch.save(self.model_conv, name)

    @staticmethod
    def load(path):
        return torch.load(path)

    def evaluate(self, testloader, batch_transforms=True):
        if batch_transforms:
            transforms = get_resnet18_batch_transforms()
        correct = 0
        total = 0
        times_epochs = []

        transforms_time = 0
        with torch.no_grad():
            epoch_start = time.time()
            epoch_tt = 0
            for samples, labels in tqdm(testloader):
                samples, labels = samples.to(self.device), \
                                  labels.to(self.device)
                start_transoform = time.time()
                if batch_transforms:
                    samples = transforms(samples)
                transofrm_time = time.time() - start_transoform
                transforms_time += transofrm_time

                tt_start = time.time()
                net_out = self(samples)
                tt_end = time.time()
                epoch_tt += (tt_end - tt_start)
                for label, net_out in zip(labels, net_out):
                    predicted = torch.argmax(net_out)
                    if label == predicted:
                        correct += 1
                    total += 1
            epoch_end = time.time()
            epoch_res = epoch_end-epoch_start
            print(f'Epoch overral time: {epoch_res},'
                  f' feedforward time: {epoch_tt}')
            times_epochs.append(epoch_res)
        return round(correct/total, 3)


BATCH_SIZE = 128
MODEL_NAME = 'model.pt'


def main():
    root_train_dir = os.path.join('data', 'PetImages', 'Train')
    csv_train_file = os.path.join('data', 'train_annotations.csv')
    root_test_dir = os.path.join('data', 'PetImages', 'Test')
    csv_test_file = os.path.join('data', 'test_annotations.csv')

    preprocessed = transforms.Compose([
        transforms.Resize(256),
        transforms.CenterCrop(224),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ])

    td = LabelledDataset(csv_train_file, root_train_dir, transforms=preprocessed)
    trainloader = DataLoader(td, batch_size=BATCH_SIZE,
                             shuffle=True, num_workers=0)
    model = Model()
    model.train(trainloader, epochs=3)
    model.save(MODEL_NAME)

    td = LabelledDataset(csv_test_file, root_test_dir, transforms=preprocessed)
    testloader = DataLoader(td, batch_size=BATCH_SIZE,
                            shuffle=True, num_workers=0)

    model.evaluate(testloader)


if __name__ == "__main__":
    path1 = os.path.join('data', 'PetImages', 'Unlabelled', '4001.jpg')
    path2 = os.path.join('data', 'PetImages', 'Test', 'Cat', '2.jpg')

    device = torch.device(
        "cuda:0" if torch.cuda.is_available() else "cpu")
    preprocessed = transforms.Compose([
        transforms.Resize(256),
        transforms.CenterCrop(224),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ])
    img1 = cv2.imread(path1)
    img1 = cv2.cvtColor(img1, cv2.COLOR_BGR2RGB)
    img2 = cv2.imread(path2)
    img2 = cv2.cvtColor(img2, cv2.COLOR_BGR2RGB)
    img1 = PIL.Image.fromarray(img1)
    img2 = PIL.Image.fromarray(img2)
    img1 = preprocessed(img1).unsqueeze(0).to(device)
    img2 = preprocessed(img2).unsqueeze(0).to(device)

    model = torch.load(MODEL_NAME)
    predictions = model(img1)
    print(predictions)
    predictions = model(img2)
    print(predictions)

    model_conv = torchvision.models.resnet18(pretrained=True)
    num_ftrs = model_conv.fc.in_features
    model_conv.fc = nn.Sequential(
        nn.Linear(num_ftrs, 256),
        nn.Linear(256, 2))
    # model_conv = model_conv.to(device)
    # torch.save(model_conv, 'model_test.pt')
    # model = torch.load('model_test.pt')
    # img1 = img1.unsqueeze(0)
    # img1 = img1.to(device)
    # predictions = model(img1)
    # print(predictions)

    # model2 = torch.load(MODEL_NAME)
    # print(model2)