#!/bin/bash
# ***********************************************************************
# **  功能描述：用于脚本启动BERT模型验证
# **  创建者： 微信公众号：数据时光者
# **  创建日期： 2020-02-22
# **  修改日期   修改人   修改内容
# ***********************************************************************

# 主目录
ROOT_PATH="/home/notebook/data/group/liushuming"

# 根据具体任务来划分文件夹
TASK_PATH=${ROOT_PATH}'/first_category'


# 数据存放目录
DATA_PATH=${TASK_PATH}'/data_input'
# BERT预训练模型目录
BERT_MODEL_NAME=${ROOT_PATH}'/bert_model/tourch_bert_uncase'
# 训练集路径
TRAIN_DATA=${DATA_PATH}'/train.csv'
# 测试集路径
TEST_DATA=${DATA_PATH}'/test.csv'
# 测试集预测数据路径
TEST_PREDICT_DATA=${DATA_PATH}'/test_predict.csv'
# 模型效果路径：模型测试集的指标都在整个文件里
MODEL_EVALUATE_DATA=${DATA_PATH}'/model_evaluate_result.csv'
# 手动选择导入哪个模型
MODEL_LOAD_PATH=${TASK_PATH}'/model_dump/lsm_test_0222_2057'


python multi_tag_validate.py --bert_model_name=${BERT_MODEL_NAME} \
    --train_data=${TRAIN_DATA} \
    --test_data=${TEST_DATA} \
    --model_load_path=${MODEL_LOAD_PATH} \
    --test_predict_data=${TEST_PREDICT_DATA} \
    --model_evaluate_data=${MODEL_EVALUATE_DATA} 
