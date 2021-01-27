from typing import List, Tuple, Dict
from collections import Counter

from landing import nlp_udpipe, nlp_stanza
from utils.preprocessing import remove_stopwords
from search.query_searching import search_for_query


def get_sources_using_prakash(fragments: List[str], web_search_params) -> List[str]:
    keywords_by_chunks, chunks_lvl_imp_words, chunk_of_fragment = extract_key_phrases(fragments)
    chunks_urls = get_pages(keywords_by_chunks, chunks_lvl_imp_words, web_search_params)
    # do counting for some kind of ranking and select top_n urls
    url_count = Counter(url for chunk_urls in chunks_urls for url in chunk_urls)
    top_n_urls = [link for link, count in url_count.most_common(n=web_search_params["top_n"])]
    # selecting only top n urls for all chunks
    for i in range(len(chunks_urls)):
        chunks_urls[i] = [url for url in chunks_urls[i] if url in top_n_urls]
    # getting fragment urls from related chunk urls
    fragments_urls = []
    for i in range(len(fragments)):
        if chunk_of_fragment[i] is not None:
            fragments_urls.append(chunks_urls[chunk_of_fragment[i]])
        else:
            fragments_urls.append([])
    return fragments_urls


def extract_key_phrases(fragments: List[str]) -> Tuple[List[List[List[str]]], List[List[str]], Dict[int, int]]:
    chunks, chunk_of_fragment = get_chunks(fragments)
    chunks_lvl_imp_words, document_lvl_imp_words = get_important_words(chunks)
    keywords_by_chunks = []
    for i in range(len(chunks)):
        chunk = chunks[i]
        chunk_lvl_imp_words = chunks_lvl_imp_words[i]
        chunk_lvl_imp_word = chunk_lvl_imp_words[0]
        first_subgroup_of_sents, second_subgroup_of_sents, whole_chunk_words = get_subgroups(chunk,
                                                                                             chunk_lvl_imp_word,
                                                                                             document_lvl_imp_words)
        chunk_keywords = get_keywords(first_subgroup_of_sents, second_subgroup_of_sents, whole_chunk_words)
        keywords_by_chunks.append(chunk_keywords)
    return keywords_by_chunks, chunks_lvl_imp_words, chunk_of_fragment


def get_pages(keywords_by_chunks: List[List[List[str]]], chunks_lvl_imp_words: List[List[str]], params) \
        -> List[List[str]]:
    chunks_relevant_urls = []
    for i in range(len(keywords_by_chunks)):
        queries = get_queries(chunk_keywords=keywords_by_chunks[i], chunk_lvl_imp_words=chunks_lvl_imp_words[i])
        resulted_urls = conditional_search(queries, params)
        chunks_relevant_urls.append(resulted_urls)
    return chunks_relevant_urls


def get_chunks(fragments: List[str]) -> Tuple[List[str], Dict[int, int]]:
    # cases when a new chunk is created:
    # 1. current fragment is a title
    # 2. previous fragment was not a title and the current is a title or has length >100 words
    # 3. after previous merge the chunk exceed 200 words size
    # +. if fragment is the very fist one
    # stopwords are filtered out from resulted chunks
    chunks = []
    previous_fragment_is_a_title = False
    previous_chunk_is_over = False
    chunk_of_fragment = {}
    i = 0
    for fragment in fragments:
        fragment_is_empty = not fragment
        fragment_words_count = len(fragment.split())
        current_fragment_is_a_title = fragment_words_count < 9
        if not fragment_is_empty:
            if current_fragment_is_a_title and not previous_fragment_is_a_title or \
                    not previous_fragment_is_a_title and fragment_words_count > 100 or previous_chunk_is_over or \
                    not chunks:
                chunks.append(fragment)
            else:
                chunks[-1] += ' ' + fragment
            previous_chunk_is_over = len(chunks[-1].split()) > 200
            previous_fragment_is_a_title = current_fragment_is_a_title
            chunk_of_fragment[i] = len(chunks) - 1
        else:
            chunk_of_fragment[i] = None
            previous_fragment_is_a_title = False
        i += 1
    chunks = [remove_stopwords(chunk)for chunk in chunks]
    return chunks, chunk_of_fragment


def get_important_words(chunks: List[str]) -> Tuple[List[List[str]], List[str]]:
    # term frequencies (chunk level and document level) are counted without stopwords and short words(with length <3)
    chunk_lvl_tfs = Counter()
    doc_lvl_tfs = Counter()
    chunks_lvl_imp_words = []
    for i in range(len(chunks)):
        chunk_lvl_tfs.clear()
        chunk_words = [word.text for word in nlp_udpipe(chunks[i])]
        for word in chunk_words:
            if len(word) > 3:
                chunk_lvl_tfs[word] += 1
                doc_lvl_tfs[word] += 1
        chunks_lvl_imp_words.append([word for word, _ in chunk_lvl_tfs.most_common()])
    document_lvl_imp_words = [word for word, _ in doc_lvl_tfs.most_common(n=5)]
    return chunks_lvl_imp_words, document_lvl_imp_words


def get_subgroups(chunk: str, chunk_lvl_imp_word: str, doc_lvl_imp_words: List[str]) -> \
        Tuple[List[Tuple[str, str]], List[Tuple[str, str]], List[Tuple[str, str]]]:
    # sub grouping sentences within i-th chunk into 2 groups
    # 1. first group contains sentences that:
    #    a) have >2 document level important words, if the chunk contains >5 sentences
    #    b) have any document document level important word, if the chunk contains <5 sentences
    # 2. second group contains sentences that:
    #    a) have any document level and any chunk level important words
    #    b) have any chunk level important word, if the chunk contains <5 sentences
    nlp_chunk = nlp_stanza(chunk)
    sents_words = [[(w.text.lower(), w.pos) for w in sent.words] for sent in nlp_chunk.sentences]
    whole_chunk_words = [item for sublist in sents_words for item in sublist]
    sents_count_in_chunk = len(nlp_chunk.sentences)
    first_subgroup_of_sents = []
    second_subgroup_of_sents = []
    for sent_words in sents_words:
        doc_lvl_imp_words_occ = sum(sent_word[0] in doc_lvl_imp_words for sent_word in sent_words)
        chunk_lvl_imp_word_occ = any(sent_word[0] == chunk_lvl_imp_word for sent_word in sent_words)
        if sents_count_in_chunk > 5 and doc_lvl_imp_words_occ > 2 or \
                sents_count_in_chunk < 5 and doc_lvl_imp_words_occ > 0:
            first_subgroup_of_sents.extend(sent_words)

        elif chunk_lvl_imp_word_occ and doc_lvl_imp_words_occ > 0 or \
                chunk_lvl_imp_word_occ and sents_count_in_chunk < 5:
            second_subgroup_of_sents.extend(sent_words)
    return first_subgroup_of_sents, second_subgroup_of_sents, whole_chunk_words


def get_keywords(first_subgroup: List[str], second_subgroup: List[str], whole_chunk_group: List[str]) -> \
        List[List[str]]:
    # extracting keywords from three groups(first_subgroup, second_subgroup, whole_chunk_group)
    chunk_keywords = []
    word_count = Counter()
    for group in [first_subgroup, second_subgroup, whole_chunk_group]:
        if group:
            for word, pos in group:
                if pos == 'NOUN':
                    word_count[word] += 1
        chunk_keywords.append([word for word, count in word_count.most_common()])
        word_count.clear()
    return chunk_keywords


def get_queries(chunk_keywords: List[List[str]], chunk_lvl_imp_words: List[str]) -> List[List[str]]:
    # for received chunk keywords 4 queries are created:
    # 1. the first contains keywords from the first subgroup
    # 2. the second contains keywords from the second subgroup
    # if the number of them is less than 6 NOUNS from the chunk itself are added to form query with length 10
    # 3. contains keywords from the whole chunk
    # 4. contains chunk level important words
    keywords_count = 10
    queries = []
    j = 0
    for i in range(0, 2):
        if len(chunk_keywords[i]) >= keywords_count:
            queries.append(chunk_keywords[i][:keywords_count])
        else:
            queries.append(chunk_keywords[i])
        if queries[-1] and len(queries[i]) < 6:
            while len(queries[-1]) < keywords_count and j < len(chunk_keywords[2]):
                if chunk_keywords[2][j] not in queries[i]:
                    queries[-1].append(chunk_keywords[2][j])
                j += 1
    queries.append(chunk_keywords[2][:keywords_count])
    queries.append(chunk_lvl_imp_words[:keywords_count])
    return queries


def conditional_search(queries: List[List[str]], kwargs) -> List[str]:
    max_requests_per_chunk = kwargs['max_requests_per_chunk']
    required_results_per_chunk = kwargs['required_results_per_chunk'] \
        if 'required_results_per_chunk' in kwargs.keys() else None
    # queries are submitted conditionally:
    # each query must have >=60% difference from the previous ones, otherwise will be dropped
    # the third query is submitted if the first one is empty or returns no result
    # the forth query is submitted if the second one is empty or dropped
    # all resulted links for chunks are counted and the top n=required_results_per_chunk is return
    results = {}
    query_is_empty_or_dropped = [len(query) == 0 for query in queries]
    counter = Counter()
    for i in range(4):
        if not results.keys() or not max_requests_per_chunk or len(results.keys()) < max_requests_per_chunk:
            if not query_is_empty_or_dropped[i]:
                for j in range(i - 1):
                    dif = [word for word in queries[i] + queries[j] if word not in queries[i] or i not in queries[j]]
                    if len(dif) / (len(queries[i]) + len(queries[j])) < 0.6:
                        query_is_empty_or_dropped[i] = True
                        break
            if not query_is_empty_or_dropped[i]:
                if i == 0:
                    results[i] = search_for_query(queries[i], kwargs)
                    query_is_empty_or_dropped[i] = not results[i]
                elif i == 1:
                    results[i] = search_for_query(queries[i], kwargs)
                elif i == 2 and query_is_empty_or_dropped[0]:
                    results[i] = search_for_query(queries[i], kwargs)
                elif i == 3 and query_is_empty_or_dropped[1]:
                    results[i] = search_for_query(queries[i], kwargs)
            if i in results.keys():
                counter.update(results[i])
    required_results_per_chunk = len(counter) if not required_results_per_chunk else required_results_per_chunk
    merged_results_list = [url for url, count in counter.most_common(n=required_results_per_chunk)]
    return merged_results_list
