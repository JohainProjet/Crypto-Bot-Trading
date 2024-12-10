import torch
from torch import nn

class NeuralNetwork_Analytic_Integration(nn.Module):
    def __init__(self, input_size, hidden_size1, output_size):
        super(NeuralNetwork_Analytic_Integration, self).__init__()
        self.layer1 = nn.Linear(input_size, hidden_size1)
        self.relu = nn.ReLU()
        self.layer2 = nn.Linear(hidden_size1, output_size)

    def forward(self, x):
        x = self.layer1(x)
        x = self.relu(x)
        x = self.layer2(x)
        return x

model = NeuralNetwork_Analytic_Integration()

"""
def stock_datas():
    global list_tensors

    final_list = [float(item) for sublist in order_book["asks"] for item in sublist]
    list_bids = [float(item) for sublist in order_book["bids"] for item in sublist]
    final_list.extend(list_bids)
    
    new_tensor = torch.tensor(final_list)
    
    list_tensors.append(new_tensor)


def stack_tensors():
    global list_tensors

    X = torch.stack(list_tensors)
    return X

"""