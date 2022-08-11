#!/usr/bin/python

import sys, getopt, logging, os, re, json, datetime, csv

INPUT=sys.argv[1:] if len(sys.argv) > 1 else ["logtestdns.log"]

logger = logging.getLogger(__name__)
logger_write = logger.getChild('write')
logger_main = logger.getChild('main')
logger_read_dig_entry = logger.getChild('read_dig_entry')
logger_process_answer = logger.getChild('process_answer')
logger_process_flags  = logger.getChild('process_flags_block')

WHEN=re.compile(";; WHEN: (.+)")
ELAPSED=re.compile(";; Query time: (\d+ \w+)")
SERVER=re.compile(";; SERVER: (.+)$")
HEADER=re.compile(";; ->>HEADER<<- .+ status: (.+), id: (\d+)$")
DIG=re.compile("^; <<>> DiG \S+ <<>> (\S+) .+")

def write(source_path, data):
    filename = source_path + '.csv' 
    logger_write.debug("CSV file name is: %s" % (filename))
    with open(filename, 'w', encoding='UTF8', newline='') as f:
        writer = csv.writer(f)

        # write the header
        writer.writerow(['Status', 'Answer','NS', 'Elapsed', 'Date'])

        # write multiple rows
        writer.writerows(data)

def process_flags_block(flags_block):
    ret = {}
    if flags_block:
        match = re.search(r', ANSWER: (\d+),', flags_block)
        if match:
            ret['answer'] = int(match.group(1))
        else:
            logger_process_flags.warning('No match for flags block: %s' % (flags_block))
    else:
        logger_process_flags.warning('Flags block is missing')
    return ret

def process_answer(answer_block, initial_timestamp, final_timestamp):
    ret = {}
    nq = 0
    logger_process_answer.debug('Answer block is: %s' % (answer_block))
    for i, answer_entry in enumerate(answer_block):
        if re.match(r";; QUESTION SECTION:", answer_entry):
            question_header = answer_block[i]
            question_footer = answer_block[i+1]
            logger_process_answer.debug(f'Question section is:\n{question_header}\n{question_footer}')
        elif re.match(r";; ANSWER SECTION:", answer_entry):
            answer_header = answer_block[i]
            logger_process_answer.debug(f'Answer header section is:\n{answer_header}')
            ret['description'] = answer_block[i+1:i+nq+1]
        elif re.match(r";; ->>HEADER<<-", answer_entry):
            logger_process_answer.debug(f'Header section is:\n{answer_block[i]}')
            header = HEADER.search(answer_entry)
            if header:
                ret['status'] = status = header.group(1)
                identifier = header.group(2)
                if status == 'NOERROR':
                    logger_process_answer.debug("\tOK status detected between '%s' and '%s' for id: %s" % (initial_timestamp, final_timestamp, identifier))
                else:
                    ret['description'] = 'N/A'
                    if status == 'REFUSED' or status == 'NXDOMAIN':
                        fqdn = answer_block[0].split()[5]
                        logger_process_answer.warn("\tNOK status '%s' detected between '%s' and '%s' while searching for:\n\t\t%s" % (status, initial_timestamp, final_timestamp, fqdn))
                    else:
                        logger_process_answer.warning('Unexpected status: %s' % (answer_entry))
            else:
                logger_process_answer.warning('No status in: %s' % (answer_entry))
        elif re.match(r";; flags:", answer_entry):
            logger_process_answer.debug(f'Flags section is:\n{answer_block[i]}')
            flags = process_flags_block(answer_entry)
            nq = flags['answer']
        elif re.match(r";; OPT PSEUDOSECTION:", answer_entry):
            pass
        elif re.match(r";; AUTHORITY SECTION:", answer_entry):
            pass
        else:
            when = WHEN.search(answer_entry)
            if when:
                date = when.group(1)
                x = datetime.datetime.strptime(date, "%a %b %d %H:%M:%S %Z %Y")
                logger_process_answer.debug('When: %s' % (x))
                ret['date'] = x.strftime("%Y/%m/%d %H:%M:%S")
            else:
                elapsed=ELAPSED.search(answer_entry)
                if elapsed:
                    e = elapsed.group(1)
                    logger_process_answer.debug('Time spent: %s' % (e))
                    ret['elapsed'] = e
                else:
                    server=SERVER.search(answer_entry)
                    if server:
                        s = server.group(1)
                        logger_process_answer.debug('NS: %s' % (s))
                        ret['name_server'] = s
                    else:
                        pass
    return ret

class ConnectionTimeoutError(Exception):
    """Raised when connection timeout"""
    pass

def read_dig_entry(block):
    ret = {}
    determinant_entry = block[4]
    initial_timestamp = block[0]
    final_timestamp = block[-1]
    if re.match(r";; connection timed out; no servers could be reached", determinant_entry):
        command = block[2]
        logger_read_dig_entry.warn("\tConnection timeout detected between '%s' and '%s' while executing:\n\t\t%s" % (initial_timestamp, final_timestamp, command))
        raise ConnectionTimeoutError(determinant_entry)
    if re.match(r";; Got answer:", determinant_entry):
        logger_read_dig_entry.debug('Got answer: %s' % (block))
        return process_answer(block[2:-2], initial_timestamp, final_timestamp)
    raise Exception(determinant_entry)

def main():
    for source_path in INPUT:
        data_collection = []
        logger_main.info('Processing %s' % (source_path))
        with open(source_path,"r") as datafile:
            block = []
            for line in datafile:
                if re.match(r"^-+$", line): #Last line
                    logger_main.debug('Processing block %s' % (block))
                    try:
                        de = read_dig_entry(block)
                        for d in de['description']:
                            data_collection.append([de['status'], d, de['name_server'], de['elapsed'], de['date']])
                    except ConnectionTimeoutError as cte: 
                        logger_main.debug(f'Connection t/o detected: {cte}')
                    except KeyError as e: 
                        raise Exception(block) from e
                    finally:
                        block = []
                else:
                    block.append(line.rstrip())
        write(source_path, data_collection)

if __name__ == '__main__':
    logging.basicConfig(format='%(asctime)s %(levelname)s %(message)s', filename='%s_%s.log' % (os.path.splitext(sys.argv[0])[0], datetime.datetime.now().strftime("%Y%m%d-%H%M%S")), filemode='w', level=logging.DEBUG)
    logging.getLogger().addHandler(logging.StreamHandler())
    logger_write.setLevel(logging.INFO)
    logger_main.setLevel(logging.INFO)
    logger_read_dig_entry.setLevel(logging.INFO)
    logger_process_answer.setLevel(logging.INFO)
    logger_process_flags.setLevel(logging.INFO)
    main()
