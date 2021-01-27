import itertools
from typing import List
import datetime

from account.manager import get_current_user
from database.documents import Documents
from report.report import FragmentReport
from document.document import Fragment, Document
from search.prakash import get_sources_using_prakash


def upload_similar_docs_from_web(fragments: List[Fragment], **params):
    fragments_url_snippet_pairs = get_url_snippet_pairs(fragments, params)

    for url, snippet in set(itertools.chain.from_iterable(fragments_url_snippet_pairs)):
        doc = Document(
            id=None,
            uri=url,
            snippet=snippet,
            date_added=datetime.datetime.now(),
            user_login=params["user_login"])
        Documents.add_document(doc)


def get_candidate_fragments_from_web(fragments: List[Fragment], **params) -> List[FragmentReport]:
    fragments_url_snippet_pairs = get_url_snippet_pairs(fragments, params)
    # create reports
    reports = []
    url_doc = {}
    user_login, _ = get_current_user()
    for i in range(len(fragments)):
        similar_fragments = []
        for url, snippet in fragments_url_snippet_pairs[i]:
            if url not in url_doc.keys():
                doc = Document(
                    id=None,
                    uri=url,
                    snippet=snippet,
                    date_added=datetime.datetime.now(),
                    user_login=user_login)
                url_doc[url] = doc
            web_doc_fragments = url_doc[url].get_fragments()
            similar_fragments.extend([(wb_fragment, 1.0) for page in web_doc_fragments for wb_fragment in page])
        reports.append(FragmentReport(checked_fragment=fragments[i], most_similar=similar_fragments))
    return reports


def get_url_snippet_pairs(fragments: List[Fragment], params) -> List[List[str,str]]:
    # get fragment related urls by specified key phrase extraction algorithm
    fragments = [fragment.text for fragment in fragments]
    web_search_params = params["WEB_SEARCH"]
    algorithm = web_search_params["source_extraction_algorithm"]
    return source_retrieval_algorithms[algorithm](fragments, web_search_params)


source_retrieval_algorithms = {
    "prakash": get_sources_using_prakash
}
