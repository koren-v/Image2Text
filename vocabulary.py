import nltk
import pickle
import os.path
import numpy as np
from pycocotools.coco import COCO
from collections import Counter


class Vocabulary(object):
    def __init__(self,
                 vocab_threshold,
                 vocab_file='./vocab.pkl',
                 glove_file='./glove.pkl', 
                 start_word="<start>",
                 end_word="<end>",
                 unk_word="<unk>",
                 annotations_file='./cocoapi/annotations/captions_train2014.json',
                 vocab_from_file=False, 
                 embedd_dimension=300,
                 dataset='coco'):

        self.vocab_threshold = vocab_threshold
        self.vocab_file = vocab_file
        self.glove_file = glove_file
        self.start_word = start_word
        self.end_word = end_word
        self.unk_word = unk_word
        self.num_special_words = 3
        self.annotations_file = annotations_file
        self.vocab_from_file = vocab_from_file
        self.embedd_dimension = embedd_dimension
        self.dataset = dataset
        self.get_vocab()

        # to set them during vocab creation
        self.word2idx = None
        self.idx2word = None
        self.weight_matrix = None
        self.idx = None
        self.glove = None

    def get_vocab(self):
        """Load the vocabulary from file OR build the vocabulary from scratch."""
        if os.path.exists(self.vocab_file) & self.vocab_from_file:
            with open(self.vocab_file, 'rb') as f:
                vocab = pickle.load(f)
                self.word2idx = vocab.word2idx
                self.idx2word = vocab.idx2word
                self.weight_matrix = vocab.weight_matrix
            print('Vocabulary successfully loaded from vocab.pkl file!')
        else:
            self.build_vocab()
            with open(self.vocab_file, 'wb') as f:
                pickle.dump(self, f)
        
    def build_vocab(self):
        """Populate the dictionaries for converting tokens to integers (and vice-versa)."""
        self.init_vocab()
        self.load_glove_dict()
        self.add_captions()
        self.add_word(self.start_word)
        self.add_word(self.end_word)
        self.add_word(self.unk_word)

    def init_vocab(self):
        """Initialize the dictionaries for converting tokens to integers (and vice-versa)."""
        self.word2idx = {}
        self.idx2word = {}
        self.idx = 0

    def load_glove_dict(self):
        with open(self.glove_file, 'rb') as f:
            self.glove = pickle.load(f)

    def add_word(self, word):
        """Add a token to the vocabulary."""
        if word not in self.word2idx:
            self.word2idx[word] = self.idx
            self.idx2word[self.idx] = word
            try:
                self.weight_matrix[self.idx] = self.glove[word]
            except KeyError:
                self.weight_matrix[self.idx] = np.random.normal(scale=0.6, size=(self.embedd_dimension,))
            self.idx += 1

    def add_captions(self):
        """Loop over training captions and add all tokens to the vocabulary that meet or exceed the threshold."""
        counter = Counter()
        if self.dataset == 'coco':
            coco = COCO(self.annotations_file)
            ids = coco.anns.keys()
            data = coco.anns
        elif self.dataset == 'insta':
            insta = pickle.load(open(self.annotations_file, 'rb'))
            ids = list(insta.keys())  
            data = insta 
        for i, idx in enumerate(ids):
            caption = str(data[idx]['caption'])
            tokens = nltk.tokenize.word_tokenize(caption.lower())
            counter.update(tokens)
            if i % 100000 == 0:
                print("[%d/%d] Tokenizing captions..." % (i, len(ids)))

        words = [word for word, cnt in counter.items() if cnt >= self.vocab_threshold]
        self.weight_matrix = np.zeros((len(words)+self.num_special_words,self.embedd_dimension))
        for i, word in enumerate(words):
            self.add_word(word)

    def __call__(self, word):
        if word not in self.word2idx:
            return self.word2idx[self.unk_word]
        return self.word2idx[word]

    def __len__(self):
        return len(self.word2idx)
