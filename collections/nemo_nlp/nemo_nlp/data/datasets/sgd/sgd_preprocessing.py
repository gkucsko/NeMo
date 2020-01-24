"""
Some parts of this code were adapted from 
https://github.com/google-research/google-research/tree/master/schema_guided_dst
"""

import os

import collections
import numpy as np

import nemo
import nemo_nlp
from  nemo_nlp.utils import nlp_utils
from nemo_nlp.data.datasets.sgd import data_utils
from nemo_nlp.modules import sgd_modules


class SchemaPreprocessor:
    """ 
    Convert the raw data to the standard format supported by
    StateTrackingSGDData.
    
    Args:
        data_dir (str) - Directory for the downloaded DSTC8 data, which contains
            the dialogue files and schema files of all datasets (eg train, dev)
        dialogues_example_dir (str) - Directory where preprocessed DSTC8 dialogues are stored
        schema_embedding_dir (str) - Directory where .npy file for embedding of
            entities (slots, values, intents) in the dataset_split's
            schema are stored.
        task_name (str) - The name of the task to train
        vocab_file (str) - The path to BERT vocab file
        do_lower_case - (bool) - Whether to lower case the input text.
            Should be True for uncased models and False for cased models.
        max_seq_length (int) - The maximum total input sequence length after
            WordPiece tokenization. Sequences longer than this will be
            truncated, and sequences shorter than this will be padded."
        tokenizer - tokenizer
        bert_model - pretrained BERT model
        dataset_split (str) - Dataset split for training / prediction (train/dev/test)
        overwrite_dial_file (bool) - Whether to generate a new file saving
            the dialogue examples overwrite_schema_emb_file,
        bert_ckpt_dir (str) - Directory containing pre-trained BERT checkpoint
        nf - NeuralModuleFactory
    """
    def __init__(self,
                 data_dir,
                 schema_embedding_dir,
                 max_seq_length,
                 tokenizer,
                 bert_model,
                 dataset_split,
                 overwrite_schema_emb_file,
                 bert_ckpt_dir,
                 nf):

        # processor = data_utils.Dstc8DataProcessor(
        #       data_dir,
        #       train_file_range=data_utils.FILE_RANGES[task_name]["train"],
        #       dev_file_range=data_utils.FILE_RANGES[task_name]["dev"],
        #       test_file_range=data_utils.FILE_RANGES[task_name]["test"],
        #       vocab_file=vocab_file,
        #       do_lower_case=do_lower_case,
        #       tokenizer=tokenizer,
        #       max_seq_length=max_seq_length)

        # # Generate the dialogue examples if needed or specified.
        # dial_file_name = f"{task_name}_{dataset_split}_examples.processed"
        # self.dial_file = os.path.join(dialogues_example_dir,
        #                               dial_file_name)

        # if not os.path.exists(dialogues_example_dir):
        #     os.makedirs(dialogues_example_dir)
        # if not os.path.exists(self.dial_file) or overwrite_dial_file:
        #     nemo.logging.info("Start generating the dialogue examples.")
        #     data_utils._create_dialog_examples(processor,
        #                                        self.dial_file,
        #                                        dataset_split)
        #     nemo.logging.info(f"The dialogue examples saved at {self.dial_file}")
        #     nemo.logging.info("Finish generating the dialogue examples.")

        self.schema_embedding_file = os.path.join(schema_embedding_dir,
            f"{dataset_split}_pretrained_schema_embedding.npy")

        # Generate the schema embeddings if needed or specified.
        if not os.path.exists(self.schema_embedding_file) or overwrite_schema_emb_file:
            nemo.logging.info("Start generating the schema embeddings.")
            # create schema embedding if no file exists
            schema_json_path = os.path.join(data_dir, 
                                            dataset_split,
                                            "schema.json")

            emb_datalayer = nemo_nlp.BertInferDataLayer(dataset_type='SchemaEmbeddingDataset',
                                                        tokenizer=tokenizer,
                                                        max_seq_length=max_seq_length,
                                                        input_file=schema_json_path)
            
            input_ids, input_mask, input_type_ids = emb_datalayer()
            hidden_states = bert_model(input_ids=input_ids,
                                       token_type_ids=input_type_ids,
                                       attention_mask=input_mask)

            evaluated_tensors = nf.infer(tensors=[hidden_states],
                                         checkpoint_dir=bert_ckpt_dir)

            hidden_states = [nlp_utils.concatenate(tensors) for tensors in evaluated_tensors]
            emb_datalayer.dataset.save_embeddings(hidden_states,
                                                  self.schema_embedding_file)

            nemo.logging.info(f"The schema embeddings saved at {self.schema_embedding_file}")
            nemo.logging.info("Finish generating the schema embeddings.")

    def _get_schema_embeddings(self):
        if not os.path.exists(self.schema_embedding_file):
            raise ValueError(f"{self.schema_embedding_file} not found. ")

        with open(self.schema_embedding_file, "rb") as f:
            schema_data = np.load(f, allow_pickle=True)

        # Convert from list of dict to dict of list
        schema_data_dict = collections.defaultdict(list)
        for service in schema_data:
            schema_data_dict["cat_slot_emb"].append(service["cat_slot_emb"])
            schema_data_dict["cat_slot_value_emb"].append(service["cat_slot_value_emb"])
            schema_data_dict["noncat_slot_emb"].append(service["noncat_slot_emb"])
            schema_data_dict["req_slot_emb"].append(service["req_slot_emb"])
            schema_data_dict["intent_emb"].append(service["intent_emb"])
        
        return schema_data_dict

      # def _decode_record(record, name_to_features, schema_tensors):
      #   """Decodes a record to a TensorFlow example."""

      #   example = tf.parse_single_example(record, name_to_features)

      #   # tf.Example only supports tf.int64, but the TPU only supports tf.int32.
      #   # So cast all int64 to int32.
      #   for name in list(example.keys()):
      #     t = example[name]
      #     if t.dtype == tf.int64:
      #       t = tf.cast(t, tf.int32)
      #     example[name] = t

      #   # Here we need to insert schema's entity embedding to each example.

      #   # Shapes for reference: (all have type tf.float32)
      #   # "cat_slot_emb": [max_num_cat_slot, hidden_dim]
      #   # "cat_slot_value_emb": [max_num_cat_slot, max_num_value, hidden_dim]
      #   # "noncat_slot_emb": [max_num_noncat_slot, hidden_dim]
      #   # "req_slot_emb": [max_num_total_slot, hidden_dim]
      #   # "intent_emb": [max_num_intent, hidden_dim]

      #   service_id = example["service_id"]
      #   for key, value in schema_tensors.items():
      #     example[key] = value[service_id]
      #   return example