from keras import backend as K
from keras.models import Model
from keras.layers import Input, Dense, Add, Average, Lambda, BatchNormalization
from scipy.io import loadmat
from keras.callbacks import EarlyStopping, ModelCheckpoint
from keras.backend import clear_session
from keras import models
from keras import layers
import numpy as np
from contextlib import redirect_stdout
from keras.models import load_model

#Hyper-parameters#
num_networks = 20
num_montecarlo = 5
testRatio = 15/100
trainRatio = 70/100
valRatio = 15/100
frac = 0.999

#Initializing variables#
percentErrors = np.zeros(num_montecarlo)
cmind = []
test_ind = [0]*num_montecarlo
net_com_mc = []

#Load in the data#
inputs = loadmat('tfdata.mat')
t = inputs['t_orig']
p = inputs['p_orig']


def myprint(s):
    with open('modelsummary.txt','w+') as f:
        print(s, file=f)


def confusionwithindex(targets, predictions):
    cm = np.zeros(shape=(2,2))
    ind = [[[] for i in range(2)] for j in range(2)]
    for l in range(len(targets)):
        if targets[l][0] == 0 and predictions[l]:  #False Positive
            cm[0,1] += 1
            ind[0][1].append(l)
        if targets[l][0] == 1 and predictions[l]:  #True Positive
            cm[0,0] += 1
            ind[0][0].append(l)
        if targets[l][0] == 0 and not predictions[l]:  #True Negative
            cm[1,1] += 1
            ind[1][1].append(l)
        if targets[l][0] == 1 and not predictions[l]:  #False Negative
            cm[1,0] += 1
            ind[1][0].append(l)
    return cm, ind


def findMisclass(q, cmind, frac):
    m = num_montecarlo
    sum10 = []
    sum01 = []
    sum11 = []
    sum00 = []
    for i in range(m):
        sum10.extend(cmind[i][1][0])
        sum01.extend(cmind[i][0][1])
        sum11.extend(cmind[i][1][1])
        sum00.extend(cmind[i][0][0])
    n10, _ = np.histogram(sum10, bins=range(q))
    n01, _ = np.histogram(sum01, bins=range(q))
    n11, _ = np.histogram(sum11, bins=range(q))
    n00, _ = np.histogram(sum00, bins=range(q))
    n = n10 + n01
    ind = np.where(n > (m*frac))
    ind10 = np.where(n10 >= (m*frac))
    ind01 = np.where(n01 >= (m*frac))
    ind11 = np.where(n11 >= (m*frac))
    ind00 = np.where(n00 >= (m*frac))
    return n, n10, n01, ind, ind10, ind01, ind11, ind00


def sensspec(cmind):
    mc = len(cmind)
    sens = np.zeros(mc)
    spec = np.zeros(mc)
    for i in range(mc):
        spec[i] = len(cmind[i][0][0]) / (len(cmind[i][0][0]) + len(cmind[i][0][1]))
        sens[i] = len(cmind[i][1][1]) / (len(cmind[i][1][0]) + len(cmind[i][1][1]))
    avgsens = np.mean(sens)
    stdsens = np.std(sens)
    avgspec = np.mean(spec)
    stdspec = np.std(spec)
    return avgsens, stdsens, avgspec, stdspec


def preminmax(p):
    minp = np.amin(p, 0)
    maxp = np.amax(p, 0)

    equal = np.equal(minp, maxp)
    nequal = np.logical_not(equal)

    if sum(equal) != 0:
        print('Some maximums and minimums are equal. Those inputs won''t be transformed.')
        minp0 = minp*nequal - 1*equal
        maxp0 = maxp*nequal + 1*equal
    else:
        minp0 = minp
        maxp0 = maxp

    minp0 = np.expand_dims(minp0, axis=0)
    maxp0 = np.expand_dims(maxp0, axis=0)
    pn = 2*(p-minp0)/(maxp0-minp0) - 1
    return pn, minp, maxp


def vote(models, model_input):
    yModels = [model(model_input) for model in models]
    ytot = []
    for model in yModels:
        ytot.append(model)
    decision = layers.concatenate(ytot)
    committee = Model(inputs=model_input,outputs=decision,name='committee')
    return committee


def ensemblemodel(models, model_input):
    yModels = [model(model_input) for model in models]
    yAvg = Average()(yModels)
    committee = Model(inputs=model_input,outputs=yAvg,name='committee')
    return committee


def fit_model():
    model_inputs = Input(shape=p[0].shape)
    inputs_shortcut = model_inputs
    layer1 = Dense(244, activation='relu')(model_inputs)
    layer1 = BatchNormalization()(layer1)
    layer2 = Dense(244, activation='relu')(layer1)
    layer2 = BatchNormalization()(layer2)
    layer2 = Add()([layer2, inputs_shortcut])
    layer2_shortcut = layer2
    layer3 = Dense(244, activation='relu')(layer2)
    layer3 = BatchNormalization()(layer3)
    layer4 = Dense(244, activation='relu')(layer3)
    layer4 = BatchNormalization()(layer4)
    layer4 = Add()([layer4, layer2_shortcut])
    layer5 = Dense(244, activation='relu')(layer4)
    layer5 = BatchNormalization()(layer5)
    outputs = Dense(2, activation='softmax')(layer5)
    net = Model(inputs=model_inputs, outputs=outputs)
    net.compile(loss='binary_crossentropy', optimizer='adam', metrics=['accuracy'])
    return net

    # net = models.Sequential()
    # net.add(layers.Dense(units=300, activation='relu', input_shape=p[0].shape))
    # net.add(layers.BatchNormalization())
    # net.add(layers.Dense(units=300, activation='relu'))
    # net.add(layers.BatchNormalization())
    # net.add(layers.Dense(units=300, activation='relu'))
    # net.add(layers.BatchNormalization())
    # net.add(layers.Dense(units=300, activation='relu'))
    # net.add(layers.BatchNormalization())
    # net.add(layers.Dense(units=300, activation='relu'))
    # net.add(layers.BatchNormalization())
    # net.add(layers.Dense(units=2, activation='softmax'))
    # net.compile(loss='binary_crossentropy', optimizer='adam', metrics=['accuracy'])
    # return net


# def fit_model():
#     net = models.Sequential()
#     net.add(layers.Dense(units=600, activation='relu', input_shape=p[0].shape))
#     net.add(layers.Dropout(0.2))
#     net.add(layers.Dense(units=600, activation='relu'))
#     net.add(layers.Dropout(0.5))
#     net.add(layers.Dense(units=600, activation='relu'))
#     net.add(layers.Dropout(0.5))
#     net.add(layers.Dense(units=600, activation='relu'))
#     net.add(layers.Dropout(0.5))
#     net.add(layers.Dense(units=600, activation='relu'))
#     net.add(layers.Dense(units=2, activation='softmax'))
#     net.compile(loss='binary_crossentropy', optimizer='adam', metrics=['accuracy'])
#     return net

#Early stopping not currently being used, batch norm instead#
callbacks = [EarlyStopping(monitor='val_loss', patience=20),
             ModelCheckpoint(filepath='best_model.h5', monitor='val_loss', save_best_only=True)]


#Normalize the training data#
inputs, _, _ = preminmax(p)

inputs1 = inputs
t1 = t

#This loops over the number of Monte Carlo trials#
for j in range(num_montecarlo):

    x = inputs1
    y = t1
    net_committee = [0]*num_networks
    tr_comm = [0]*num_networks

    #Here we randomly remove our test set from the training data#
    randInd = np.random.permutation(len(x))
    testInd = randInd[:int(len(x)*testRatio)-1]
    test_ind[j] = testInd
    xtest = x[testInd]
    ytest = y[testInd]
    x = np.delete(x, testInd, axis=0)
    y = np.delete(y, testInd, axis=0)

    #This loop will train a committee of neural networks#
    for i in range(num_networks):

        #Create a committee member by calling our fit_model() function#
        net_committee[i] = fit_model()

        #Shuffle training data#
        ix = np.random.permutation(len(y))
        x = x[ix]
        y = y[ix]

        #Train one committee member using early stopping#
        tr_comm[i] = net_committee[i].fit(x=x,  # Features
                          y=y,  # Target vector
                          epochs=300,  # Number of epochs
                         # callbacks=callbacks,  #uncomment for Early stopping
                          verbose=0,  # Print description after each epoch
                          batch_size=len(y),  # Number of observations per batch
                          validation_split=valRatio, # Data for evaluation
                          shuffle=False)

    #Definig the input to the graph#
    model_input = Input(shape=x[0].shape)

    #Creating a committee using the vote function#
    committee = vote(net_committee, model_input)

    #Save committee#
    committee.save('/home/dhagan/seq2seq-fingerprint/committee' + str(j))

    #Run test data through a committee and get the outputs from last 2 neurons on the test set#
    xx = committee.predict(xtest, batch_size=len(ytest), verbose=0, steps=None)

    #Initialize variable to hold committee decision on the test set#
    decisiontest = []

    #This loop checks the output of committee members to determine their vote:
    # True for good binder, False for bad. Then adds this to decisiontest#
    for i in range(0,num_networks*2,2):
        decisiontest.append(xx[:,i]>0.5)

    #Converting decisiontest to an array#
    decisiontest = np.array(decisiontest)

    #Summing the votes of the committee members gives the final decision:#
    #if more than half the networks predict good binder the result is True and if not it is False#
    decisiontest = np.sum(decisiontest, axis=0) >= (num_networks/2)

    #Check the decisions versus the labels and divide by length of the test set to calculate % error#
    percentErrors[j] = sum(decisiontest != ytest[:,0])/len(ytest)
    print(percentErrors[j])

    #Run all data through a committee and get the outputs from last 2 neurons#
    #on the full dataset#
    decision = committee.predict(inputs, batch_size=len(y), verbose=0, steps=None)

    #Summing the votes of the committee members gives the final decision:#
    #if more than half the networks predict good binder the result is True and if not it is False#
    decision = np.int_(decision[:,0]+.5)

    #The confusionwithindex function returns a confusion matrix along with the indices of all complexes#
    #in each quandrant of the confusion matrix.#
    cm, ind = confusionwithindex(t, decision)

    #Adding the indices for complexes in the confusion matrix after each monte carlo trial.#
    cmind.append(ind)

    import matplotlib.image as mpimg
    import matplotlib.pyplot as plt

    # -----------------------------------------------------------
    # Retrieve a list of list results on training and test data
    # sets for each training epoch
    # -----------------------------------------------------------
    acc = tr_comm[1].history['acc']
    val_acc = tr_comm[1].history['val_acc']
    loss = tr_comm[1].history['loss']
    val_loss = tr_comm[1].history['val_loss']

    epochs = range(len(acc))  # Get number of epochs

    # ------------------------------------------------
    # Plot training and validation accuracy per epoch
    # ------------------------------------------------
    plt.plot(epochs, acc, 'r')
    plt.plot(epochs, val_acc, 'b')
    plt.title('Train and Validation Accuracy')
    plt.xlabel("Epochs")
    plt.ylabel("Accuracy")
    plt.legend(["Training", "Validation"])
    plt.figure()
    plt.show()

    # ------------------------------------------------
    # Plot training and validation loss per epoch
    # ------------------------------------------------
    plt.plot(epochs, loss, 'r')
    plt.plot(epochs, val_loss, 'b')
    plt.title('Training and Validation Loss')
    plt.xlabel("Epochs")
    plt.ylabel("Loss")
    plt.legend(["Training", "Validation"])
    plt.figure()
    plt.show()

    epochs_zoom = epochs[200:]
    acc_zoom = acc[200:]
    val_acc_zoom = val_acc[200:]
    loss_zoom = loss[200:]
    val_loss_zoom = val_loss[200:]

    # ------------------------------------------------
    # Plot Zoomed Accuracy
    # ------------------------------------------------
    plt.plot(epochs_zoom, acc_zoom, 'r')
    plt.plot(epochs_zoom, val_acc_zoom, 'b')
    plt.title('Accuracy Zoomed')
    plt.xlabel("Epochs")
    plt.ylabel("Accuracy")
    plt.legend(["Training", "Validation"])
    plt.figure()
    plt.show()

    # ------------------------------------------------
    # Plot Zoomed Loss
    # ------------------------------------------------
    # plt.plot(epochs_zoom, loss_zoom, 'r')
    # plt.plot(epochs_zoom, val_loss_zoom, 'b')
    # plt.title('Loss Zoomed')
    # plt.xlabel("Epochs")
    # plt.ylabel("Loss")
    # plt.legend(["Training", "Validation"])
    # plt.figure()
    # plt.show()

    #Now we need to clear the graph before starting the next monte carlo trial so the committees#
    #can be trained again from scratch#
    clear_session()

    #Printing the number of the monte carlo trial that just finished.#
    #Mostly to monitor progress during training#
    print('j: ', j)

#After all monte carlo trials are finished, we write cmind to a file.#
with open('confusionmatrix', 'wb') as pickle_file:
    np.save(pickle_file, np.array(cmind))

#Get confusion matrix and indices over the full dataset and prints this to the command line (optional)#
cm, ind = confusionwithindex(t,decision)
print(cm)

#The sensspec fuction calculates average sensitivity and specificity with standard deviation#
#using cmind#
avgsens, stdsens, avgspec, stdspec = sensspec(cmind)

#The findMissclass function finds the numbers and indices of complexes that were miss-classified#
#more than frac percent of the time over the monte carlo trials. It also tells whether they are#
#True Positive or False Negative.#
n, n10, n01, ind, ind10, ind01, ind11, ind00 = findMisclass(len(inputs), cmind, frac)

#Writing the percent errors and sensitivity/specificity to a file.#
f = open('tfnnscoredata.txt', 'w+')
f.write('Average Percent Errors: ' + str(np.mean(percentErrors)) + '\n')
f.write('STD Percent Errors: ' + str(np.std(percentErrors)) + '\n')
f.write('Average Sensitivity: ' + str(avgsens) + '\n')
f.write('STD Sensitivity: ' + str(stdsens) + '\n')
f.write('Average Specificity: ' + str(avgspec) + '\n')
f.write('STD Specificity: ' + str(stdspec) + '\n')
f.write('Percent Errors for each Monte Carlo trial: ' + '\n')
for k in range(len(percentErrors)):
    f.write(str(percentErrors[k]) + '\n')
f.close()

#Append a summary of the model used to tfnnscoredata.txt#
model = fit_model()
with open('tfnnscoredata.txt', 'a') as f:
    with redirect_stdout(f):
        model.summary()


