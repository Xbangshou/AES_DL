import time
import torch
import transformers as ppb
import warnings
import numpy as np
from sklearn.model_selection import KFold
from sklearn.metrics import cohen_kappa_score
from baseline_keras import get_model
import tensorflow as tf
from preprocess import prepare_data
from visualize import plot_accuracy_curve

#####
# Hyperparameters
Hidden_dim1 = 300
Hidden_dim2 = 64
return_sequences = True
dropout = 0.5
recurrent_dropout = 0.4
input_size = 768
activation = 'relu'
optimizer = 'adam'
loss_function = 'mean_square_error'
batch_size = 64
epoch = 70
model_name = "BiLSTM"
#####

dataset_path = './data/training_set_rel3.tsv'

def train_bert_sets():
    warnings.filterwarnings('ignore')
    # Sets experiment BERT
    data, target, sets = prepare_data(dataset_path=dataset_path)
    set_count = 1
    all_sets_score = []
    for s in sets:
        print("\n--------SET {}--------\n".format(set_count))
        X = s
        y = s['domain1_score']
        cv = KFold(n_splits=5, shuffle=True)
        results = []
        fold_count = 1
        cuda = torch.device('cuda')
        cv_data = cv.split(X)
        model_class, tokenizer_class, pretrained_weights = (
            ppb.DistilBertModel, ppb.DistilBertTokenizer, 'distilbert-base-uncased')
        tokenizer = tokenizer_class.from_pretrained(pretrained_weights)
        model = model_class.from_pretrained(pretrained_weights).to(cuda)
        for traincv, testcv in cv_data:
            print("\n--------Fold {}--------\n".format(fold_count))
            X_train, X_test, y_train, y_test = X.iloc[traincv], X.iloc[testcv], y.iloc[traincv], y.iloc[testcv]
            train_essays = X_train['essay']
            test_essays = X_test['essay']
            tokenized_train = train_essays.apply(
                (lambda x: tokenizer.encode(x, add_special_tokens=True, max_length=200)))
            tokenized_test = test_essays.apply(
                (lambda x: tokenizer.encode(x, add_special_tokens=True, max_length=200)))
            max_len = max(max(len(i) for i in tokenized_train), max(len(i) for i in tokenized_test))
            padded_train = np.array([i + [0] * (max_len - len(i)) for i in tokenized_train.values])
            attention_mask_train = np.where(padded_train != 0, 1, 0)
            train_input_ids = torch.tensor(padded_train).to(cuda)
            train_attention_mask = torch.tensor(attention_mask_train).to(cuda)
            with torch.no_grad():
                last_hidden_states_train = model(train_input_ids, attention_mask=train_attention_mask)
            train_features = last_hidden_states_train[0][:, 0, :].cpu().numpy()
            padded_test = np.array([i + [0] * (max_len - len(i)) for i in tokenized_test.values])
            attention_mask_test = np.where(padded_test != 0, 1, 0)
            test_input_ids = torch.tensor(padded_test).to(cuda)
            test_attention_mask = torch.tensor(attention_mask_test).to(cuda)
            with torch.no_grad():
                last_hidden_states_test = model(test_input_ids, attention_mask=test_attention_mask)
            test_features = last_hidden_states_test[0][:, 0, :].cpu().numpy()
            train_x, train_y = train_features.shape
            test_x, test_y = test_features.shape
            trainDataVectors = np.reshape(train_features, (train_x, 1, train_y))
            testDataVectors = np.reshape(test_features, (test_x, 1, test_y))
            lstm_model = get_model(Hidden_dim1=Hidden_dim1, Hidden_dim2=Hidden_dim2,
                                   return_sequences=return_sequences,
                                   dropout=dropout, recurrent_dropout=recurrent_dropout, input_size=input_size,
                                   activation=activation,
                                   loss_function=loss_function, optimizer=optimizer, model_name=model_name)
            lstm_model.to(cuda)
            history = lstm_model.fit(trainDataVectors, y_train, batch_size=batch_size, epochs=epoch)
            plot_accuracy_curve(history)
            y_pred = lstm_model.predict(testDataVectors)
            y_pred = np.around(y_pred)
            np.nan_to_num(y_pred)
            result = cohen_kappa_score(y_test.values, y_pred, weights='quadratic')
            print("Kappa Score: {}".format(result))
            results.append(result)
            fold_count += 1
            torch.cuda.empty_cache()
            tf.keras.backend.clear_session()

        all_sets_score.append(results)
        print("Average kappa score value is : {}".format(np.mean(np.asarray(results))))
        set_count += 1

if __name__ == '__main__':
    train_bert_sets()
