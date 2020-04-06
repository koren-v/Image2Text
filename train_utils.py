import os
import sys
import math
import copy
import torch
import numpy as np
import torch.utils.data as data
from nltk.translate.bleu_score import sentence_bleu, SmoothingFunction

chencherry = SmoothingFunction()

def collect_preds(raw_preds, outputs):
    if len(raw_preds)==0:
      raw_preds = outputs.cpu().detach().numpy()
    else:
      raw_preds = np.vstack((raw_preds, outputs.cpu().detach().numpy()))
    return raw_preds
        
def compute_metric(target, preds):
    preds = torch.argmax(preds, axis=2)
    assert preds.shape == target.shape
    bleu_score = 0.0
    for pred, ground_truth in zip(preds, target):
        bleu_score += sentence_bleu([ground_truth.tolist()], pred.tolist(), smoothing_function=chencherry.method6)
    return bleu_score/len(target)

def epoch(model, phase, device, criterion, optimizer, 
          data_loader, scheduler=None):

    encoder = model['encoder']
    decoder = model['decoder']

    if phase=='train': 
        encoder.train()
        decoder.train()
    else: 
        encoder.eval()
        decoder.eval()

    running_loss = 0.0
    batches_skiped = 0
    targets = np.array([])
    raw_preds = np.array([])
    
    vocab_size = len(data_loader.dataset.vocab)
    total_steps = math.ceil(len(data_loader.dataset.caption_lengths)\
                             / data_loader.batch_sampler.batch_size)

    for step in range(total_steps):
        
        indices = data_loader.dataset.get_train_indices()        
        new_sampler = data.sampler.SubsetRandomSampler(indices=indices)
        data_loader.batch_sampler.sampler = new_sampler

        try:
            images, captions = next(iter(data_loader))
        except:
            batches_skiped+=1
            continue

        images = images.to(device)
        captions = captions.to(device)

        optimizer.zero_grad()
        with torch.set_grad_enabled(phase == 'train'):

            features = encoder(images)
            features = features.to(device)
            outputs = decoder(features, captions)

            loss = criterion(outputs.view(-1, vocab_size), captions.view(-1))

            if phase == 'train':
                loss.backward()
                optimizer.step()
                if scheduler: scheduler.step()

        running_loss += loss.item() * features.size(0)
        bleu4 = compute_metric(captions, outputs)

        stats = 'Step [{}/{}], Loss: {:.4f}, BLEU-4: {:.4f}'.format(step, total_steps, loss.item(), bleu4)

        print('\r' + stats, end="")
        sys.stdout.flush()
    
    epoch_loss = running_loss / len(data_loader.dataset.caption_lengths) #len of the data
    epoch_bleu = bleu4 / total_steps
    epoch_dict = {'batches_skiped':batches_skiped,
                  'epoch_loss': epoch_loss, 
                  'epoch_bleu': epoch_bleu,
                  'encoder': encoder,
                  'decoder': decoder}
    return epoch_dict

def fit(model, criterion, optimizer, dataloader_dict,
        num_epochs, device, stage, scheduler=None, last_epoch=None):
  
    best_loss = float('inf')
    train_loss = []
    valid_loss = []

    for i in range(num_epochs):
        print('Epoch {}/{}'.format(i+1, num_epochs))
        print('*'*40)
        for phase in ['train', 'val']:

            epoch_dict = epoch(model, phase, device, criterion, optimizer, 
                               dataloader_dict[phase], scheduler=scheduler)
            
            print('{} epoch loss: {:.4f} '.format(phase , epoch_dict['epoch_loss']))
            print('{} epoch metric: {:.4f} '.format(phase , epoch_dict['epoch_bleu']))

            if phase == 'train': train_loss.append(epoch_dict['epoch_loss'])
            else: valid_loss.append(epoch_dict['epoch_loss'])

            model_name = '{}_{:.2f}_val_{:.2f}_tr_{}.pth'.format(i+last_epoch if last_epoch else i,
                                                                 valid_loss[-1],
                                                                 train_loss[-1],
                                                                 stage)

            torch.save(epoch_dict['decoder'].state_dict(),
                        os.path.join('./models', 'decoder'+model_name))
            torch.save(epoch_dict['encoder'].state_dict(),
                        os.path.join('./models', 'encoder'+model_name))            

            # not implemented loading best model weights callback
            # if phase == 'val' and best_loss>epoch_dict['epoch_loss']:
            #     best_encoder_wts = copy.deepcopy(epoch_dict['encoder'].state_dict())
            #     best_decoder_wts = copy.deepcopy(epoch_dict['decoder'].state_dict())
            #     best_loss = epoch_dict['epoch_loss']
        print()
    print('Batches skipped', epoch_dict['batches_skiped'])
    #print('Best validation loss: {:4f}'.format(float(best_loss)))
    #metrics = {'train_loss': train_loss, 'valid_loss': valid_loss}