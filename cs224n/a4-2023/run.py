#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
CS224N 2022-23: Homework 4
run.py: Run Script for Simple NMT Model
Pencheng Yin <pcyin@cs.cmu.edu>
Sahil Chopra <schopra8@stanford.edu>
Vera Lin <veralin@stanford.edu>
Siyan Li <siyanli@stanford.edu>

Usage:
    run.py train --train-src=<file> --train-tgt=<file> --dev-src=<file> --dev-tgt=<file> --vocab=<file> [options]
    run.py decode [options] MODEL_PATH TEST_SOURCE_FILE OUTPUT_FILE
    run.py decode [options] MODEL_PATH TEST_SOURCE_FILE TEST_TARGET_FILE OUTPUT_FILE

Options:
    -h --help                               show this screen.
    --cuda                                  use GPU
    --train-src=<file>                      train source file
    --train-tgt=<file>                      train target file
    --dev-src=<file>                        dev source file
    --dev-tgt=<file>                        dev target file
    --vocab=<file>                          vocab file
    --seed=<int>                            seed [default: 0]
    --batch-size=<int>                      batch size [default: 32]
    --embed-size=<int>                      embedding size [default: 256]
    --hidden-size=<int>                     hidden size [default: 256]
    --clip-grad=<float>                     gradient clipping [default: 5.0]
    --log-every=<int>                       log every [default: 10]
    --max-epoch=<int>                       max epoch [default: 30]
    --input-feed                            use input feeding
    --patience=<int>                        wait for how many iterations to decay learning rate [default: 5]
    --max-num-trial=<int>                   terminate training after how many trials [default: 5]
    --lr-decay=<float>                      learning rate decay [default: 0.5]
    --beam-size=<int>                       beam size [default: 10]
    --sample-size=<int>                     sample size [default: 5]
    --lr=<float>                            learning rate [default: 0.001]
    --uniform-init=<float>                  uniformly initialize all parameters [default: 0.1]
    --save-to=<file>                        model save path [default: model.bin]
    --valid-niter=<int>                     perform validation after how many iterations [default: 2000]
    --dropout=<float>                       dropout [default: 0.3]
    --max-decoding-time-step=<int>          maximum number of decoding time steps [default: 70]
"""
import torch
from time import time
from tqdm import tqdm
from docopt import docopt
from numpy import random, exp
from typing import List, Tuple, Dict
from sacrebleu import corpus_bleu
from torch.nn.utils import clip_grad_norm_
from torch.utils.tensorboard import SummaryWriter
from nmt_model import Hypothesis, NMT
from utils import SentType, SentsType, read_corpus, batch_iter
from vocab import Vocab


PathType = List[List[Hypothesis]]


def evaluate_ppl(model: NMT, dev_data: List[Tuple[SentType, SentType]], batch_size: int=32) -> float:
    """ Evaluate perplexity on dev sentences
    @param model: NMT Model
    @param dev_data: list of tuples containing source and target sentence
    @param batch_size: (batch size)
    @returns ppl (perplixty on dev sentences)
    """
    was_training = model.training
    model.eval()

    cum_loss = 0.
    cum_tgt_words = 0.

    # no_grad() signals backend to throw away all gradients
    with torch.no_grad():
        for src_sents, tgt_sents in batch_iter(dev_data, batch_size):
            loss = -model(src_sents, tgt_sents).sum()

            cum_loss += loss.item()
            tgt_word_num_to_predict = sum(len(s[1:]) for s in tgt_sents)  # omitting leading `<s>`
            cum_tgt_words += tgt_word_num_to_predict

        ppl = exp(cum_loss / cum_tgt_words)

    if was_training:
        model.train()

    return ppl


def compute_corpus_level_bleu_score(references: SentsType, hypotheses: List[Hypothesis]) -> float:
    """ Given decoding results and reference sentences, compute corpus-level BLEU score.
    @param references: a list of gold-standard reference target sentences
    @param hypotheses: a list of hypotheses, one for each reference
    @returns bleu_score: corpus-level BLEU score
    """
    # remove the start and end tokens
    if references[0][0] == '<s>':
        references = [ref[1:-1] for ref in references]
    
    # detokenize the subword pieces to get full sentences
    detokened_refs = [''.join(pieces).replace('▁', ' ') for pieces in references]
    detokened_hyps = [''.join(hyp.value).replace('▁', ' ') for hyp in hypotheses]

    # sacreBLEU can take multiple references (golden example per sentence) but we only feed it one
    bleu = corpus_bleu(detokened_hyps, [detokened_refs])

    return bleu.score


def train(args: Dict[str, str]) -> None:
    """ Train the NMT Model.
    @param args: args from cmd line
    """
    from sys import stderr
    from os.path import dirname, abspath
    location = dirname(abspath(__file__))

    # EDIT: NEW VOCAB SIZE
    train_data_src = read_corpus(args['--train-src'], source=f'{location}/outputs/src', vocab_size=21000)
    train_data_tgt = read_corpus(args['--train-tgt'], source=f'{location}/outputs/tgt', vocab_size=8000)

    dev_data_src = read_corpus(args['--dev-src'], source=f'{location}/outputs/src', vocab_size=3000)
    dev_data_tgt = read_corpus(args['--dev-tgt'], source=f'{location}/outputs/tgt', vocab_size=2000)

    train_data = list(zip(train_data_src, train_data_tgt))
    dev_data = list(zip(dev_data_src, dev_data_tgt))

    train_batch_size = int(args['--batch-size'])
    clip_grad = float(args['--clip-grad'])
    valid_niter = int(args['--valid-niter'])
    log_every = int(args['--log-every'])
    model_save_path = args['--save-to']
    vocab = Vocab.load(args['--vocab'])

    # EDIT: 4X EMBED AND HIDDEN SIZES
    # model = NMT(embed_size=int(args['--embed-size']),
    #             hidden_size=int(args['--hidden-size']),
    #             dropout_rate=float(args['--dropout']),
    #             vocab=vocab)

    model = NMT(embed_size=1024, hidden_size=768, dropout_rate=float(args['--dropout']), vocab=vocab)
    
    tensorboard_path = "nmt" if args['--cuda'] else "nmt_local"
    writer = SummaryWriter(log_dir=f"{location}/outputs/runs/{tensorboard_path}")
    model.train()

    uniform_init = float(args['--uniform-init'])
    if abs(uniform_init) > 0.:
        print('uniformly initialize parameters [-%f, +%f]' % (uniform_init, uniform_init), file=stderr)
        for p in model.parameters():
            p.data.uniform_(-uniform_init, uniform_init)

    vocab_mask = torch.ones(len(vocab.tgt))
    vocab_mask[vocab.tgt['<pad>']] = 0

    if args['--cuda']:
        assert torch.cuda.is_available()
        device = torch.cuda.current_device()
    else:
        device = 'cpu'
    print(f'use device: {device}', file=stderr)

    model = model.to(device)

    optimizer = torch.optim.Adam(model.parameters(), lr=float(args['--lr']))
    # optimizer = torch.optim.Adam(model.parameters(), lr=5e-5)                       # EDIT: SMALLER LEARNING RATE

    num_trial = 0
    train_iter = patience = cum_loss = report_loss = cum_tgt_words = report_tgt_words = 0
    cum_examples = report_examples = epoch = valid_num = 0
    hist_valid_scores = []
    train_time = begin_time = time()
    print('begin Maximum Likelihood training')

    while True:
        epoch += 1

        for src_sents, tgt_sents in batch_iter(train_data, batch_size=train_batch_size, shuffle=True):
            train_iter += 1

            optimizer.zero_grad()

            batch_size = len(src_sents)

            example_losses = -model(src_sents, tgt_sents)   # (batch_size,)
            batch_loss = example_losses.sum()
            loss = batch_loss / batch_size

            loss.backward()

            # clip gradient
            grad_norm = clip_grad_norm_(model.parameters(), clip_grad)

            optimizer.step()

            batch_losses_val = batch_loss.item()
            report_loss += batch_losses_val
            cum_loss += batch_losses_val

            tgt_words_num_to_predict = sum(len(s[1:]) for s in tgt_sents)  # omitting leading `<s>`
            report_tgt_words += tgt_words_num_to_predict
            cum_tgt_words += tgt_words_num_to_predict
            report_examples += batch_size
            cum_examples += batch_size

            if train_iter % log_every == 0:
                writer.add_scalar("loss/train", report_loss / report_examples, train_iter)
                writer.add_scalar("perplexity/train", exp(report_loss / report_tgt_words), train_iter)
                print('epoch %d, iter %d, avg. loss %.2f, avg. ppl %.2f '
                      'cum. examples %d, speed %.2f words/sec, time elapsed %.2f sec' % (
                            epoch, train_iter, report_loss / report_examples, exp(report_loss / report_tgt_words),
                            cum_examples, report_tgt_words / (time() - train_time), time() - begin_time
                      ), file=stderr)

                train_time = time()
                report_loss = report_tgt_words = report_examples = 0.

            # perform validation
            if train_iter % valid_niter == 0:
                writer.add_scalar("loss/val", cum_loss / cum_examples, train_iter)
                print('epoch %d, iter %d, cum. loss %.2f, cum. ppl %.2f cum. examples %d' % (
                            epoch, train_iter, cum_loss / cum_examples, exp(cum_loss / cum_tgt_words), cum_examples
                      ), file=stderr)

                cum_loss = cum_examples = cum_tgt_words = 0.
                valid_num += 1

                print('begin validation ...', file=stderr)

                # compute dev. ppl and bleu
                dev_ppl = evaluate_ppl(model, dev_data, batch_size=128)   # dev batch size can be a bit larger
                valid_metric = -dev_ppl

                writer.add_scalar("perplexity/val", dev_ppl, train_iter)
                print('validation: iter %d, dev. ppl %f' % (train_iter, dev_ppl), file=stderr)

                is_better = len(hist_valid_scores) == 0 or valid_metric > max(hist_valid_scores)
                hist_valid_scores.append(valid_metric)

                if is_better:
                    patience = 0
                    print('save currently the best model to [%s]' % model_save_path, file=stderr)
                    model.save(model_save_path)

                    # also save the optimizers' state
                    torch.save(optimizer.state_dict(), model_save_path + '.optim')
                elif patience < int(args['--patience']):
                    patience += 1
                    print('hit patience %d' % patience, file=stderr)

                    if patience == int(args['--patience']):
                        num_trial += 1
                        print('hit #%d trial' % num_trial, file=stderr)
                        if num_trial == int(args['--max-num-trial']):
                            print('early stop!', file=stderr)
                            exit(0)

                        # decay lr, and restore from previously best checkpoint
                        lr = optimizer.param_groups[0]['lr'] * float(args['--lr-decay'])
                        print('load previously best model and decay learning rate to %f' % lr, file=stderr)

                        # load model
                        params = torch.load(model_save_path, map_location=lambda storage, loc: storage)
                        model.load_state_dict(params['state_dict'])
                        model = model.to(device)

                        print('restore parameters of the optimizers', file=stderr)
                        optimizer.load_state_dict(torch.load(model_save_path + '.optim'))

                        # set new lr
                        for param_group in optimizer.param_groups:
                            param_group['lr'] = lr

                        # reset patience
                        patience = 0

            # hard stop
            if epoch == int(args['--max-epoch']):
                print('reached maximum number of epochs!', file=stderr)
                model.save(f'{model_save_path}.{epoch}')
                exit(0)


def decode(args: Dict[str, str]) -> None:
    """ Performs decoding on a test set, and save the best-scoring decoding results.
    If the target gold-standard sentences are given, the function also computes
    corpus-level BLEU score.
    @param args: args from cmd line
    """
    from sys import stderr
    from os.path import dirname, abspath
    location = dirname(abspath(__file__))

    print("load test source sentences from [{}]".format(args['TEST_SOURCE_FILE']), file=stderr)
    test_data_src = read_corpus(args['TEST_SOURCE_FILE'], source=f'{location}/outputs/src', vocab_size=3000)
    if args['TEST_TARGET_FILE']:
        print("load test target sentences from [{}]".format(args['TEST_TARGET_FILE']), file=stderr)
        test_data_tgt = read_corpus(args['TEST_TARGET_FILE'], source=f'{location}/outputs/tgt', vocab_size=2000)
    else:
        test_data_tgt = list()

    print("load model from {}".format(args['MODEL_PATH']), file=stderr)
    model = NMT.load(args['MODEL_PATH'])

    if args['--cuda']:
        assert torch.cuda.is_available()
        device = torch.cuda.current_device()
    else:
        device = 'cpu'
    print(f'use device: {device}', file=stderr)
    model = model.to(device)

    # EDIT: BEAM SIZE USED TO BE 5
    hypotheses = beam_search(model, test_data_src, beam_size=int(args['--beam-size']),
                             max_decoding_time_step=int(args['--max-decoding-time-step']))

    if args['TEST_TARGET_FILE']:
        top_hypotheses = [hyps[0] for hyps in hypotheses]
        bleu_score = compute_corpus_level_bleu_score(test_data_tgt, top_hypotheses)
        print('Corpus BLEU: {}'.format(bleu_score), file=stderr)

    with open(args['OUTPUT_FILE'], 'w') as f:
        for src_sent, hyps in zip(test_data_src, hypotheses):
            top_hyp = hyps[0]
            hyp_sent = ''.join(top_hyp.value).replace('▁', ' ')
            f.write(hyp_sent + '\n')


def beam_search(model: NMT, test_data_src: SentsType, beam_size: int, max_decoding_time_step: int) -> PathType:
    """ Run beam search to construct hypotheses for a list of src-language sentences.
    @param model: NMT Model
    @param test_data_src: List of sentences (words) in source language, from test set.
    @param beam_size: beam_size (# of hypotheses to hold for a translation at every step)
    @param max_decoding_time_step: maximum sentence length that Beam search can produce
    @returns hypotheses (List[List[Hypothesis]]): List of Hypothesis translations for every source sentence.
    """
    from sys import stdout

    was_training = model.training
    model.eval()

    hypotheses = []
    with torch.no_grad():
        for src_sent in tqdm(test_data_src, desc='Decoding', file=stdout):
            example_hyps = model.beam_search(src_sent, beam_size=beam_size,
                                             max_decoding_time_step=max_decoding_time_step)

            hypotheses.append(example_hyps)

    if was_training:
        model.train(was_training)

    return hypotheses


def main():
    """ Main func.
    """
    args = docopt(__doc__)

    # Check pytorch version
    assert torch.__version__ >= '1.0.0'

    # seed the random number generators
    seed = int(args['--seed'])
    torch.manual_seed(seed)
    if args['--cuda']:
        torch.cuda.manual_seed(seed)
    random.seed(seed * 13 // 7)

    if args['train']:
        train(args)
    elif args['decode']:
        decode(args)
    else:
        raise RuntimeError('invalid run mode')


if __name__ == '__main__':
    main()
