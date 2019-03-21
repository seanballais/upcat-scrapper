import sys
import collections

import requests
import json
from bs4 import BeautifulSoup


def _scrape_page(page_url):
    page = requests.get(page_url)
    soup = BeautifulSoup(page.text, 'html.parser')

    passers = list()
    html_passers_table = soup.find_all('table')[2:3]
    html_passers_tbody = html_passers_table[0].find_all('tbody')[0]
    html_passers_row = html_passers_tbody.find_all('tr')

    num_passers = len(html_passers_row)
    for index in range(num_passers):
        record = html_passers_row[index]
        
        data = record.find_all('td')
        name = data[0].text.strip()
        campus = data[1].text.strip()
        course = data[2].text.strip()

        passers.append({
            'name': name,
            'campus': campus,
            'course': course
        })

    return passers


def _scrape_results(root_url, start, end):
    passers = list()
    for page_count in range(start, end + 1):
        url = '{}/page-{}.html'.format(root_url, str(page_count).zfill(3))
        passers_subset = _scrape_page(url)
        passers.extend(passers_subset)

    return passers


def _write_json(passers):
    with open('passers.json', 'w') as passers_file:
        json.dump(passers, passers_file)

    print('Finished writing JSON data to "passers.json"...')


def _write_sql(passers):
    queries = list()

    # Create the tables.
    queries.append('CREATE TABLE campuses IF NOT EXISTS ('
                   + 'id SERIAL PRIMARY KEY, '
                   + 'name TEXT NOT NULL UNIQUE'
                   + ');')
    queries.append('CREATE TABLE courses IF NOT EXISTS ('
                   + 'id SERIAL PRIMARY KEY, '
                   + 'name TEXT NOT NULL UNIQUE'
                   + ');')
    queries.append('CREATE TABLE passers IF NOT EXISTS ('
                   + 'id SERIAL PRIMARY KEY, '
                   + 'name TEXT NOT NULL, '
                   + 'course_id INTEGER REFERENCES courses(id) '
                   +           'ON DELETE SET NULL, '
                   + 'campus_id INTEGER REFERENCES campuses(id)'
                   +           'ON DELETE SET NULL'
                   + ');')

    _insert_newline_separator(queries)

    # Insert the campuses.
    tmp_campuses = sorted(list(
        set([passer['campus'] for passer in passers
             if passer['campus'] != ''])
    ))
    campuses, campus_queries = _add_insert_campuses_sql(tmp_campuses)
    queries.extend(campus_queries)

    _insert_newline_separator(queries)

    # Insert the courses.
    tmp_courses = sorted(list(
        set([passer['course'] for passer in passers
             if passer['course'] != '**Pending Case'])
    ))
    courses, course_queries = _add_insert_courses_sql(tmp_courses)
    queries.extend(course_queries)

    _insert_newline_separator(queries)

    # Insert the passers. Note that passers with a pending case will
    # be given a null value for their campus and course.


    # Just adding a bit of a new line at the end of the file as per
    # the UNIX convention.
    _insert_newline_separator(queries)

    # Time to write the SQL queries into an SQL file.
    with open('passers.sql', 'w') as passers_file:
        passers_file.write('\n'.join(queries))

    print('Finished writing SQL queries to "passers.sql".')


def _add_insert_campuses_sql(tmp_campuses):
    insert_queries = list()

    # We need this to use an OrderedDict for the campuses since we need to make
    # sure that the IDs we create for each campus maps correctly to the IDs in
    # the database.
    campuses = collections.OrderedDict()
    for v, k in enumerate(tmp_campuses):
        campuses[k] = v

    for campus in campuses.keys():
        insert_queries.append('INSERT INTO campuses(name) '
                              + 'VALUES'
                              + '(\'{}\');'.format(_escape_string(campus)))

    return campuses, insert_queries


def _add_insert_courses_sql(tmp_courses):
    insert_queries = list()

    # We need to use an OrderedDict() due to the same reasons why
    # _add_insert_campuses_sql() uses the said data structure.
    courses = collections.OrderedDict()
    for v, k in enumerate(tmp_courses):
        courses[k] = v

    for course in courses.keys():
        insert_queries.append('INSERT INTO courses(name) '
                              + 'VALUES'
                              + '(\'{}\');'.format(_escape_string(course)))

    return courses, insert_queries


def _insert_newline_separator(queries):
    # Just add a new line separator by adding a new line character to the
    # last query in the list of queries.
    last_query = queries[len(queries) - 1] + '\n'
    queries[len(queries) - 1] = last_query


def _escape_string(value):
    # This function is based on the string escape function, escape_string(),
    # of PyMySQL. The function's code can be found in:
    # - https://github.com/PyMySQL/PyMySQL/blob/master/pymysql/converters.py
    _escape_table = [unichr(x) for x in range(128)]
    _escape_table[0] = u'\\0'
    _escape_table[ord('\\')] = u'\\\\'
    _escape_table[ord('\n')] = u'\\n'
    _escape_table[ord('\r')] = u'\\r'
    _escape_table[ord('\032')] = u'\\Z'
    _escape_table[ord('"')] = u'\\"'
    _escape_table[ord("'")] = u"\\'"

    return value.translate(_escape_table)


if __name__ == '__main__':
    if len(sys.argv) != 2:
        print('Incorrect number of arguments.')
        print('Usage: ')
        print('\tpython3 upcat_scrapper.py (json | sql)')

        sys.exit(-1)
    elif sys.argv[1] not in ['json', 'sql']:
        print('Invalid output type argument. Enter \'json\' or \'sql\' only.')

        sys.exit(-1)

    output_type = sys.argv[1]

    print('Scraping records from the UPCAT results...', end=' ', flush=True)
    passers = _scrape_results('http://upcat.stickbread.net', 1, 259)

    print('Done!')
    
    if output_type == 'json':
        _write_json(passers)
    elif output_type == 'sql':
        _write_sql(passers)
