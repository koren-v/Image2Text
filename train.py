import os
import sys
import argparse

import nltk
from nltk.translate.bleu_score import sentence_bleu
from data_loader import get_loader
from torchvision import transforms

import math
import numpy as np

import torch.utils.data as data

import torch
import torch.nn as nn
import torchvision.models as models

from model import EncoderCNN, DecoderRNN
from train_utils import *

# Define a transform to pre-process the training images.
transform_train = transforms.Compose([ 
    transforms.Resize(256),                          # smaller edge of image resized to 256
    transforms.RandomCrop(224),                      # get 224x224 crop from random location
    transforms.RandomHorizontalFlip(),               # horizontally flip image with probability=0.5
    transforms.ToTensor(),                           # convert the PIL Image to a tensor
    transforms.Normalize((0.485, 0.456, 0.406),      # normalize image for pre-trained model
                         (0.229, 0.224, 0.225))])


device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")

if __name__  == "__main__":

    nltk.download('punkt')

    parser = argparse.ArgumentParser()
    parser.add_argument("num_epochs", type=int,
                        help="num of epoches")
    parser.add_argument("--encoder_lr", type=float)
    parser.add_argument("--decoder_lr", type=float)
    parser.add_argument("--stage")
    parser.add_argument("--cnn", default='resnet101')
    parser.add_argument("--vocab_from_file", action="store_true")
    parser.add_argument("--hidden_size", type=int, default=768)
    parser.add_argument("--load_model", action="store_true")
    parser.add_argument("--unfreeze_encoder", type=int)
    parser.add_argument("--num_layers", type=int, default=2)
    parser.add_argument("--batch_size", type=int, default=512)
    args = parser.parse_args()

    embed_size=512
    batch_size = args.batch_size
    num_layers = args.num_layers
    hidden_size = args.hidden_size
    vocab_threshold = 3
    vocab_from_file = args.vocab_from_file

    train_data_loader = get_loader(transform=transform_train,
                                mode='train',
                                batch_size=batch_size,
                                vocab_threshold=vocab_threshold,
                                vocab_from_file=vocab_from_file)

    val_data_loader = get_loader(transform=transform_train,
                                mode='val',
                                batch_size=batch_size,
                                vocab_from_file=True)

    dataloader_dict = {'train':train_data_loader, 'val': val_data_loader}                         
    vocab_size = len(train_data_loader.dataset.vocab)

    cnn = args.cnn

    encoder=EncoderCNN(embed_size, cnn)
    encoder=encoder.to(device)

    decoder=DecoderRNN(embed_size=512, hidden_size=hidden_size , vocab_size=vocab_size, num_layers=num_layers)
    decoder=decoder.to(device)

    if args.load_model:
        name = input('Type name of encoder/decoder')
        last_epoch = int(name[1])  
        if torch.cuda.is_available():
            encoder.load_state_dict(torch.load('./models/encoder'+name+'.pth'))
            decoder.load_state_dict(torch.load('./models/decoder'+name+'.pth'))
        else:
            encoder.load_state_dict(torch.load('./models/encoder'+name+'.pth', 
                                            map_location=torch.device('cpu')))
            decoder.load_state_dict(torch.load('./models/encoder'+name+'.pth', 
                                            map_location=torch.device('cpu')))

    num_epochs = args.num_epochs           
    decoder_lr = args.decoder_lr
    encoder_lr = args.encoder_lr
    stage = args.stage
    last_epoch = None
    
    if args.unfreeze_encoder:
        encoder.unfreeze_encoder(args.unfreeze_encoder)
        encoder_params = []
        for name,param in encoder.named_parameters():
            if param.requires_grad == True:
                encoder_params.append(param)
                print("\t",name)
    else:
        encoder_params = list(encoder.linear.parameters()) + list(encoder.bn1.parameters())

    criterion = nn.CrossEntropyLoss()
    optimizer = torch.optim.Adam(
        [
            {"params":decoder.parameters(),"lr": decoder_lr},
            {"params":encoder_params, "lr": encoder_lr},
        
        ])

    model = {'encoder' : encoder, 'decoder' : decoder}

    #optimizer = torch.optim.Adam(params,lr=learning_rate)
    # total_step = math.ceil(len(train_data_loader.dataset.caption_lengths) / train_data_loader.batch_sampler.batch_size)
    # total_val_step = math.ceil(len(val_data_loader.dataset.caption_lengths) / val_data_loader.batch_sampler.batch_size)

    print('Start Training!')

    fit(model, criterion, optimizer, dataloader_dict,
        num_epochs, device, stage, last_epoch=last_epoch)




