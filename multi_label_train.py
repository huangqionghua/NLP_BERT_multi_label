#pip install -i https://pypi.tuna.tsinghua.edu.cn/simple fastai
import numpy as np
import pandas as pd
from pathlib import Path
from typing import *
import torch
import torch.optim as optim

from fastai import *
from fastai.text import *
from fastai.callbacks import *

from sklearn.model_selection import train_test_split

from pytorch_pretrained_bert import BertTokenizer
from sklearn import metrics
from sklearn.preprocessing import Binarizer
from pytorch_pretrained_bert.modeling import BertConfig, BertForSequenceClassification
import datetime

# 将模型训练代码封装
# 通过外部传参应用到不同的任务中
import argparse
parser = argparse.ArgumentParser(description='multi_label_train model')

# 需要传递的参数
parser.add_argument('--bert_model_name', type=str, default = None)
parser.add_argument('--train_data', type=str, default = None)
parser.add_argument('--model_save_path', type=str, default = None)
parser.add_argument('--lab_flag', type=str, default = None)

args = parser.parse_args()

BERT_MODEL_NAME = args.bert_model_name
LAB_FLAG = args.lab_flag
MODEL_SAVE_PATH = args.model_save_path
TRAIN_DATA_PATH = args.train_data

# 是否启动测试
# 测试使用极少数据，目的是为了验证整个代码可以跑通
TESTING=True
EPOCH=3

# 测试集和验证集的划分
train_df = pd.read_csv(TRAIN_DATA_PATH)
train, val= train_test_split(train_df, test_size=0.3)

# 文本字段名称
OCR = "ocr"

# 自动获取多标签的种类
def get_label_cols():
    label_cols_df = train_df
    label_list = list(label_cols_df.columns)
    # ocr,label1,label2....
    list_lable_new = label_list[1:]
    return list_lable_new

LABEL_COLS = get_label_cols()
print(LABEL_COLS)
LABEL_NUMS = len(LABEL_COLS)
print(LABEL_NUMS)


class Config(dict):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        for k, v in kwargs.items():
            setattr(self, k, v)
    
    def set(self, key, val):
        self[key] = val
        setattr(self, key, val)

# testing=True   是否测试 暂时用于调通代码 如果测试，只有1024条数据
# bert_model_name bert 预训练模型存储位置，可以使用string查找的方式，也可以给个路径
# bert_model_name如果是用路径的话，会有两个文件 bert_config.json 和 pytorch_model.bin
# max_lr 最大的学习率
# epochs 训练轮数
config = Config(
    testing=TESTING,
    #bert_model_name="bert-base-uncased",
    bert_model_name=BERT_MODEL_NAME,
    max_lr=3e-5,
    epochs=EPOCH,
    use_fp16=True,
    bs=32,
    discriminative=False,
    max_seq_len=256,
)


# 如果仅用来测试调通程序，训练、验证和测试各选1024条数据
if config.testing:
    train = train.head(1024)
    val = val.head(1024)

print(train.shape)
print(val.shape)
# https://github.com/huggingface/transformers
# pytorch_pretrained_bert类似于keras_bert，是对于bert的一个封装，官方github在上面
# BertTokenizer.from_pretrained这里面的参数是一个列表，包含很多bert model，比如 BERT-Base-Chinese、BERT-Base, Multilingual ...
# 作者对于每个预训练的模型都提供了6个model类和3个tokenizer类供我们使用
# 加载词典 pre-trained model tokenizer (vocabulary)
# 函数的参数对应6中预训练的模型
# tokenizer进行初始化
bert_tok = BertTokenizer.from_pretrained(
    config.bert_model_name,
)


# Tokenized input
# 修改 fastai 的分词器使之结合到 BertTokenizer
# 在开始和结尾处分别添加 "[CLS]" 和 ["[SEP]"] 标志
class FastAiBertTokenizer(BaseTokenizer):
    """Wrapper around BertTokenizer to be compatible with fast.ai"""
    def __init__(self, tokenizer: BertTokenizer, max_seq_len: int=128, **kwargs):
        self._pretrained_tokenizer = tokenizer
        self.max_seq_len = max_seq_len

    def __call__(self, *args, **kwargs):
        return self

    def tokenizer(self, t:str) -> List[str]:
        """Limits the maximum sequence length"""
        return ["[CLS]"] + self._pretrained_tokenizer.tokenize(t)[:self.max_seq_len - 2] + ["[SEP]"]

# 使用bert的词汇表作为 fastai的词汇表
fastai_bert_vocab = Vocab(list(bert_tok.vocab.keys()))

# Tokenized input
fastai_tokenizer = Tokenizer(tok_func=FastAiBertTokenizer(bert_tok, max_seq_len=config.max_seq_len), pre_rules=[], post_rules=[])

class BertTokenizeProcessor(TokenizeProcessor):
    def __init__(self, tokenizer):
        super().__init__(tokenizer=tokenizer, include_bos=False, include_eos=False)

class BertNumericalizeProcessor(NumericalizeProcessor):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, vocab=Vocab(list(bert_tok.vocab.keys())), **kwargs)

#  tokenizer + vocab
def get_bert_processor(tokenizer:Tokenizer=None, vocab:Vocab=None):
    """
    Constructing preprocessors for BERT
    We remove sos/eos tokens since we add that ourselves in the tokenizer.
    We also use a custom vocabulary to match the numericalization with the original BERT model.
    """
    return [BertTokenizeProcessor(tokenizer=tokenizer),
            NumericalizeProcessor(vocab=vocab)]

# 基于 TextDataBunch 构造 数据器
# DataBunch是fastai中读取数据最基本的类，其针对不同的任务将数据集处理成合适的形式，以便送入learner进行训练。
# 从dataframe中读取文本数据
"""
class BertDataBunch(TextDataBunch):
    @classmethod
    def from_df(cls, path:PathOrStr, train_df:DataFrame, valid_df:DataFrame, test_df:Optional[DataFrame]=None,
                tokenizer:Tokenizer=None, vocab:Vocab=None, classes:Collection[str]=None, text_cols:IntsOrStrs=1,
                label_cols:IntsOrStrs=0, label_delim:str=None, **kwargs) -> DataBunch:
        "Create a `TextDataBunch` from DataFrames."
        p_kwargs, kwargs = split_kwargs_by_func(kwargs, get_bert_processor)
        # use our custom processors while taking tokenizer and vocab as kwargs
        processor = get_bert_processor(tokenizer=tokenizer, vocab=vocab, **p_kwargs)
        if classes is None and is_listy(label_cols) and len(label_cols) > 1: classes = label_cols
        src = ItemLists(path, TextList.from_df(train_df, path, cols=text_cols, processor=processor),
                        TextList.from_df(valid_df, path, cols=text_cols, processor=processor))
        src = src.label_for_lm() if cls==TextLMDataBunch else src.label_from_df(cols=label_cols, classes=classes)
        if test_df is not None: src.add_test(TextList.from_df(test_df, path, cols=text_cols))
        return src.databunch(**kwargs)


# 第一种数据格式
# 从dataframe 灌入数据进行训练
# train 训练集
# val 验证集
# test 测试集
# tokenizer +  vocab
# text_cols 需要识别的ocr文本，对应于我们的title
# label_cols 标签列表
databunch = BertDataBunch.from_df(".", train, val, test,
                  tokenizer=fastai_tokenizer,
                  vocab=fastai_bert_vocab,           
                  text_cols=OCR,
                  label_cols=LABEL_COLS,
                  bs=config.bs,
                  collate_fn=partial(pad_collate, pad_first=False, pad_idx=0),
             )
"""
# 第二种数据格式
databunch = TextDataBunch.from_df(".", train, val,
                  tokenizer=fastai_tokenizer,
                  vocab=fastai_bert_vocab,
                  include_bos=False,
                  include_eos=False,
                  text_cols=OCR,
                  label_cols=LABEL_COLS,
                  bs=32,
                  collate_fn=partial(pad_collate, pad_first=False, pad_idx=0),
             )

# 加载模型 pre-trained model
# 导入bert预训练模型
# num_labels=6 标签数量为6
bert_model = BertForSequenceClassification.from_pretrained(config.bert_model_name, num_labels=LABEL_NUMS)


# 针对多标签标注模型定义损失函数 
# BCELoss是(−1/n)∑(Yn×lnXn+(1−Yn)×ln(1−Xn))
# BCEWithLogitsLoss是把BCELoss+sigmod合成一步操作
loss_func = nn.BCEWithLogitsLoss()

# 模型训练
# 添加评价指标
from fastai.callbacks import *
acc_02 = partial(accuracy_thresh, thresh=0.7)


# 构建训练器
# 数据使用 databunch，模型使用 bert_model，
# 损失函数使用 loss_func， 评价指标使用 accuracy
learner = Learner(
    databunch, bert_model,
    loss_func=loss_func,
    metrics=acc_02
)



# 将模型划分成多个部分，有助于判别式学习。不同的部分使用不同的学习率和权重
def bert_clas_split(self) -> List[nn.Module]:  
    bert = bert_model.bert
    embedder = bert.embeddings
    pooler = bert.pooler
    encoder = bert.encoder
    classifier = [bert_model.dropout, bert_model.classifier]
    n = len(encoder.layer)//3
    print(n)
    groups = [[embedder], list(encoder.layer[:n]), list(encoder.layer[n+1:2*n]), list(encoder.layer[(2*n)+1:]), [pooler], classifier]
    return groups

x = bert_clas_split(bert_model)

learner.split([x[0], x[1], x[2], x[3], x[5]])

# 半精度浮点数，更低的精度可以使在内存中存放更多数据成为可能，并且减少在内存中移动进出数据的时间。
#低精度浮点数的电路也会更加简单。这些好处结合在一起，带来了明显了计算速度的提升。
if config.use_fp16: learner = learner.to_fp16()

# 寻找最佳的学习率并画出不同学习率下损失值
learner.lr_find()
learner.recorder.plot()


"""
func:模型训练
"""
def model_train():
    # 模型训练
    # 使用learning rate annealing(学习率退火算法)
    # fit_one_cycle在训练中，先使用较大的学习率，在逐步减小学习率。
    # 首先，在学习的过程中逐步增大学习率目的是为了不至于陷入局部最小值，边学习边计算loss。
    # 其次，当loss曲线向上扬即变大的时候，开始减小学习率，慢慢的趋近梯度最小值，loss也会慢慢减小。
    # 每一轮耗时12:39左右
    learner.fit_one_cycle(config.epochs, max_lr=config.max_lr)
    # 模型存储
    learner.save(MODEL_SAVE_PATH, return_path=True)

    
if __name__ == '__main__':
    
    # 记录模型训练时间
    train_start = datetime.datetime.now()
    print("begin to train")
    model_train()
    # 记录代码的结束时间
    train_end = datetime.datetime.now()
    train_dur = (train_end - train_start).seconds
    train_dur = train_dur/60
    
    # 计算耗时
    print("模型训练耗时：")
    print(train_start, train_end, train_dur)
