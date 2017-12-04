#----------------------------------------------------------------------------------------------
#  Copyright (c) Microsoft Corporation. All rights reserved.
#  Licensed under the MIT License. See License.txt in the project root for license information.
#----------------------------------------------------------------------------------------------

from mmdnn.conversion.common.DataStructure.graph import GraphNode, Graph
from tensorflow.core.framework.node_def_pb2 import NodeDef
from tensorflow.core.framework import attr_value_pb2
import torch


class PyTorchGraphNode(GraphNode):

    def __init__(self, layer, id):
        self._type = layer.__class__.__name__.replace('Backward', '')
        self._name = "{}_{}".format(self.type, id)
        super(PyTorchGraphNode, self).__init__(layer)

    @property
    def name(self):
        return self._name

    @property
    def type(self):
        return self._type


    @property
    def pth_layer(self):
        return self.layer


    def get_attr(self, name, default_value = None):
        raise NotImplementedError()
        if name in self.layer.attr:
            attr = self.layer.attr[name]
            field = attr.WhichOneof('value')
            val = getattr(attr, field) if field else default_value
            if isinstance(val, attr_value_pb2.AttrValue.ListValue):
                return list(val.ListFields()[0][1])
            else:
                return val.decode('utf-8') if isinstance(val, bytes) else val
        else:
            return default_value


class PyTorchGraph(Graph):

    def __init__(self, model):
        # sanity check.
        pass

        super(PyTorchGraph, self).__init__(model)
        self.model = model


    def build(self, shape):
        shape = tuple([1] + shape)
        dummy_input = torch.autograd.Variable(torch.randn(shape))
        output_node = self.model(dummy_input)

        search_queue = [output_node.grad_fn]
        tmp_node = PyTorchGraphNode(output_node.grad_fn, 0)
        self.layer_map[tmp_node.name] = tmp_node
        visited = {output_node.grad_fn : self.layer_map[tmp_node.name]}

        idx = 0
        node_count = 1
        while (idx < len(search_queue)):
            current_node = search_queue[idx]
            current_type = visited[current_node].type
            if hasattr(current_node, 'next_functions'):
                for parent, _ in current_node.next_functions:
                    parent_type = parent.__class__.__name__.replace('Backward', '')
                    if parent_type != 'AccumulateGrad' and \
                       (parent_type != 'Transpose' or current_type != 'Addmm'):
                        if not parent in visited:
                            tmp_node = PyTorchGraphNode(parent, node_count)
                            self.layer_map[tmp_node.name] = tmp_node
                            node_count += 1
                            visited[parent] = tmp_node
                            search_queue.append(parent)
                        self._make_connection(visited[parent].name, visited[current_node].name)
            idx += 1

        super(PyTorchGraph, self).build()
