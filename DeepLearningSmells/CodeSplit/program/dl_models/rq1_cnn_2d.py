from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import datetime
import os
import tensorflow as tf
import configuration, input_data
import inputs
import plot_util
import time
import metrics_util
import numpy as np
from sklearn.dummy import DummyClassifier

# -- Parameters ---
DIM = "2d"

# TOKENIZER_OUT_PATH = "../../data/tokenizer_out"
# OUT_FOLDER = "../results/rq1/raw"
TOKENIZER_OUT_PATH = "/users/pa18/tushar/smellDetectionML/data/tokenizer_out"
OUT_FOLDER = "/users/pa18/tushar/smellDetectionML/program/results/rq1/raw"

TRAIN_VALIDATE_RATIO = 0.7
CLASSIFIER_THRESHOLD = 0.7
# ------------


def cnn(data, config, smell, out_folder=OUT_FOLDER, dim=DIM, is_final = False):
    assert (config.layers >= 1 and config.layers <= 3)

    model = tf.keras.models.Sequential()
    model.add(tf.keras.layers.Conv2D(config.filters, config.kernel, activation='relu',
                                     input_shape=(data.max_input_height, data.max_input_width, 1),
                                     bias_initializer='zeros',
                                     kernel_initializer='random_uniform'
                                     ))
    model.add(tf.keras.layers.BatchNormalization())
    model.add(tf.keras.layers.MaxPooling2D(config.pooling_window, strides=2))
    for i in range(2, config.layers + 1):
        model.add(tf.keras.layers.Conv2D(2 * config.filters, config.kernel, activation='relu'))
        model.add(tf.keras.layers.BatchNormalization())
        model.add(tf.keras.layers.MaxPooling2D(config.pooling_window, strides=2))
        # model.add(tf.keras.layers.Dropout(rate=0.1))
    model.add(tf.keras.layers.SpatialDropout2D(rate=0.1))
    model.add(tf.keras.layers.Flatten())
    model.add(tf.keras.layers.Dense(32, activation='relu'))
    model.add(tf.keras.layers.Dense(1, activation='sigmoid'))
    model.compile(optimizer='adam',
                  loss='binary_crossentropy',
                  metrics=['accuracy'])

    model.summary()

    earlystop = tf.keras.callbacks.EarlyStopping(monitor='val_loss', min_delta=0.0001, patience=5, verbose=1, mode='auto')
    best_model_filepath = 'weights_best.cnn2d.hdf5'
    if os.path.exists(best_model_filepath):
        print("deleting the old weights file..")
        os.remove(best_model_filepath)
    checkpoint = tf.keras.callbacks.ModelCheckpoint(filepath=best_model_filepath, monitor='val_loss', verbose=1,
                                                    save_best_only=True)
    callbacks_list = [earlystop, checkpoint]

    batch_sizes = [32, 64, 128, 256]
    b_size = int(len(data.train_labels) / 512)
    if b_size > len(batch_sizes) - 1:
        b_size = len(batch_sizes) - 1

    if is_final:
        model.fit(data.train_data, data.train_labels, epochs=config.epochs, batch_size=batch_sizes[b_size],
            verbose=1, shuffle=False)
        stopped_epoch = config.epochs
    else:
        model.fit(data.train_data, data.train_labels, validation_split=0.2, epochs=config.epochs, batch_size=batch_sizes[b_size],
              callbacks=callbacks_list, verbose=1, shuffle=False)
        stopped_epoch = earlystop.stopped_epoch
        model.load_weights(best_model_filepath)

    # y_pred = model.predict_classes(data.eval_data)
    # We manually apply classification threshold
    prob = model.predict_proba(data.eval_data)
    y_pred = inputs.get_predicted_y(prob, CLASSIFIER_THRESHOLD)

    auc, accuracy, precision, recall, f1, average_precision, fpr, tpr = \
        metrics_util.get_all_metrics(model, data.eval_data, data.eval_labels, y_pred)

    if is_final:
        plot_util.save_roc_curve(fpr, tpr, auc, smell, config, out_folder, dim)
        plot_util.save_precision_recall_curve(data.eval_labels, y_pred, average_precision, smell, config, out_folder, dim, "cnn")
    tf.keras.backend.clear_session()
    return auc, accuracy, precision, recall, f1, average_precision, stopped_epoch


def get_all_data(data_path, smell):
    print("reading data...")

    # Load training and eval data
    train_data, train_labels, eval_data, eval_labels, max_input_height, max_input_width = \
        inputs.get_data_2d(data_path, OUT_FOLDER, "rq1_cnn2d_" + smell,
                           train_validate_ratio=TRAIN_VALIDATE_RATIO, max_training_samples=5000)

    print("reading data... done.")
    # just for dummy classifier
    # train_data = train_data.reshape((len(train_labels), max_input_height*max_input_width))
    # eval_data = eval_data.reshape((len(eval_labels), max_input_height*max_input_width))

    return input_data.Input_data2(train_data, train_labels, eval_data, eval_labels,
                                  max_input_height, max_input_width)


def write_result(file, str):
    f = open(file, "a+")
    f.write(str)
    f.close()


def get_out_file(smell):
    now = datetime.datetime.now()
    if not os.path.exists(OUT_FOLDER):
        os.makedirs(OUT_FOLDER)
    return os.path.join(OUT_FOLDER, "cnn2d_rq1_" + smell +
                        "_" + str(now.strftime("%d%m%Y_%H%M") + ".csv"))


def main(smell, data_path, skip_iter=-1):
    input_data = get_all_data(data_path, smell)

    conv_layers = {1, 2}
    filters = {8, 16, 32, 64}
    kernels = {5, 7, 11}
    pooling_windows = {2, 3, 4, 5}
    epochs = {50}

    total_iterations = len(conv_layers) * len(filters) * len(kernels) * len(pooling_windows) * len(epochs)
    cur_iter = 1
    outfile = get_out_file(smell)
    write_result(outfile,
                 "conv_layers,filters,kernel,max_pooling_window,epoch,stopped_epoch,auc,accuracy,precision,recall,f1,average_precision,time\n")
    for layer in conv_layers:
        for filter in filters:
            for kernel in kernels:
                for pooling_window in pooling_windows:
                    for epoch in epochs:
                        print("** Iteration {0} of {1} **".format(cur_iter, total_iterations))
                        if cur_iter < skip_iter:
                            cur_iter += 1
                            continue
                        try:
                            config = configuration.CNN_config(layer, filter, kernel, pooling_window, epoch)
                            start_time = time.time()
                            auc, accuracy, precision, recall, f1, average_precision, stopped_epoch = cnn(input_data, config, smell)
                            end_time = time.time()
                            elapsed_time = end_time - start_time
                            write_result(outfile, str(layer) + "," + str(filter) + "," + str(kernel) + "," +
                                         str(pooling_window) + "," + str(epoch) + "," + str(stopped_epoch) + "," +
                                         str(auc) + "," + str(accuracy) + "," + str(precision) + "," + str(recall)
                                         + "," + str(f1) + "," + str(average_precision) + "," +
                                         str(elapsed_time) + "\n")
                        except ValueError as error:
                            print("Skipping combination layer: {}, filter: {}, kernel: {}, pooling_window: {}"
                                  .format(layer, filter, kernel, pooling_window))
                            print(error)
                            write_result(outfile, str(layer) + "," + str(filter) + "," + str(kernel) + "," +
                                         str(pooling_window) + "," + str(epoch) + ",-1,-1,-1,-1,-1,-1,-1,-1\n")
                        cur_iter += 1

def run_cnn_with_best_params(smell, input_data, conv_layers, filter, kernel, pooling_window, epochs):
    outfile = get_out_file(smell + "final")
    write_result(outfile, "conv_layers,filters,kernel,max_pooling_window,epoch,stopped_epoch,auc,accuracy,precision,recall,f1,average_precision,time\n")

    try:
        config = configuration.CNN_config(conv_layers, filter, kernel, pooling_window, epochs)
        start_time = time.time()
        auc, accuracy, precision, recall, f1, average_precision, stopped_epoch = cnn(input_data, config, smell, is_final=True)
        end_time = time.time()
        elapsed_time = end_time - start_time
        write_result(outfile, str(conv_layers) + "," + str(filter) + "," + str(kernel) + "," +
                     str(pooling_window) + "," + str(epochs) + "," + str(stopped_epoch) + "," +
                     str(auc) + "," + str(accuracy) + "," + str(precision) + "," + str(recall)
                     + "," + str(f1) + "," + str(average_precision) + "," +
                     str(elapsed_time) + "\n")
    except ValueError as error:
        print("Skipping combination layer: {}, filter: {}, kernel: {}, pooling_window: {}"
              .format(conv_layers, filter, kernel, pooling_window))
        print(error)
        write_result(outfile, str(conv_layers) + "," + str(filter) + "," + str(kernel) + "," +
                     str(pooling_window) + "," + str(epochs) + ",-1,-1,-1,-1,-1,-1,-1,-1\n")


def run_final():
    smell = "ComplexMethod"
    data_path1 = os.path.join(os.path.join(TOKENIZER_OUT_PATH, smell), DIM)
    input_data1 = get_all_data(data_path1, smell)
    run_cnn_with_best_params(smell, input_data=input_data1, conv_layers=1, filter=64, kernel=11, pooling_window=5, epochs=36)

    smell = "ComplexConditional"
    data_path2 = os.path.join(os.path.join(TOKENIZER_OUT_PATH, smell), DIM)
    input_data2 = get_all_data(data_path2, smell)
    run_cnn_with_best_params(smell, input_data=input_data2, conv_layers=2, filter=64, kernel=7, pooling_window=2,
                             epochs=22)

    smell = "FeatureEnvy"
    data_path3 = os.path.join(os.path.join(TOKENIZER_OUT_PATH, smell), DIM)
    input_data3 = get_all_data(data_path3, smell)
    run_cnn_with_best_params(smell, input_data=input_data3, conv_layers=2, filter=16, kernel=5, pooling_window=3, epochs=14)

    smell = "MultifacetedAbstraction"
    data_path4 = os.path.join(os.path.join(TOKENIZER_OUT_PATH, smell), DIM)
    input_data4 = get_all_data(data_path4, smell)
    run_cnn_with_best_params(smell, input_data=input_data4, conv_layers=2, filter=64, kernel=11, pooling_window=2, epochs=6)


def measure_random_performance():
    smell_list = {"MultifacetedAbstraction"}
    outfile = get_out_file("random_classifier")
    write_result(outfile, "smell,auc,precision,recall,f1,average_precision\n")
    for smell in smell_list:
        data_path = os.path.join(os.path.join(TOKENIZER_OUT_PATH, smell), DIM)
        input_data = get_all_data(data_path, smell)
        input_data.eval_data = None
        input_data.train_data = None
        y_pred = np.random.randint(2, size=len(input_data.eval_labels))

        auc, precision, recall, f1, average_precision, fpr, tpr = \
            metrics_util.get_all_metrics_(input_data.eval_labels, y_pred)

        write_result(outfile, smell +"," + str(auc) +"," + str(precision) +"," + str(recall) +"," + str(f1) +"," + str(average_precision) + "\n")


def measure_performance_dummy_classifier():
    outfile = get_out_file("dummy_classifier")
    write_result(outfile, "smell,auc,precision,recall,f1,average_precision\n")
    for smell in smell_list:
        data_path = os.path.join(os.path.join(TOKENIZER_OUT_PATH, smell), DIM)
        input_data = get_all_data(data_path, smell)
        # clf = DummyClassifier(strategy='stratified', random_state=0)
        clf = DummyClassifier(strategy='most_frequent', random_state=0)
        inverted_train_labels = inputs.invert_labels(input_data.train_labels)

        clf.fit(input_data.train_data, inverted_train_labels)
        # clf.fit(input_data.train_data, input_data.train_labels)
        y_pred = clf.predict(input_data.eval_data)


        auc, precision, recall, f1, average_precision, fpr, tpr = \
            metrics_util.get_all_metrics_(input_data.eval_labels, y_pred)

        write_result(outfile, smell +"," + str(auc) +"," + str(precision) +"," + str(recall) +"," + str(f1) +"," + str(average_precision) + "\n")


if __name__ == "__main__":
    smell_list = ["ComplexConditional", "ComplexMethod", "MultifacetedAbstraction", "FeatureEnvy"]
    # smell_list = {"FeatureEnvy"}
    # for smell in smell_list:
    #     data_path = os.path.join(os.path.join(TOKENIZER_OUT_PATH, smell), DIM)
    #     inputs.preprocess_data_2d(data_path)
    #     main(smell, data_path)

    # The following is the last step to get the final results. hyper parameters seletected from the best performance (f1)
    run_final()

    # Generate baseline using random classifier
    # measure_random_performance()
    # Let's say what a dummy classifier says
    # measure_performance_dummy_classifier()