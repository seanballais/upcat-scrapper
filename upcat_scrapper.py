import sys
import collections

import requests
import json
from bs4 import BeautifulSoup


def _scrape_page(page_url):
    page = requests.get(page_url)
    soup = BeautifulSoup(page.text, 'html.parser')

    html_passers_table = soup.find_all('table')[2:3]
    html_passers_tbody = html_passers_table[0].find_all('tbody')[0]
    html_passers_row = html_passers_tbody.find_all('tr')

    num_passers = len(html_passers_row)
    passers = list()
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


def _scrape_results():
    root_url = 'https://upcat.up.edu.ph/results/'

    # We first need to get the number of pages that are in the results site.
    page = requests.get(root_url)
    soup = BeautifulSoup(page.text, 'html5lib')

    # Websites should really use IDs in their HTML elements.
    html_passers_groups_table = soup.find_all('table')[1]
    html_passers_groups_tbody = html_passers_groups_table.find_all('tbody')[0]
    num_passers_groups = len(html_passers_groups_tbody.find_all('tr'))

    passers = list()
    for page_count in range(1, num_passers_groups + 1):
        print('Scraping page #{}...'.format(page_count))

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
                   + 'course_id INTEGER REFERENCES courses(id), '
                   + 'campus_id INTEGER REFERENCES campuses(id)'
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
    for passer in passers:
        course = passer['course']
        campus = passer['campus']

        name = passer['name']
        course_id = courses[course] if course != '**Pending Case' else 'NULL'
        campus_id = campuses[campus] if campus != '' else 'NULL'

        # We are not escaping course_id and campus_id since they're integers.
        # They are also still not escaped if they are NULLs since we already
        # know that the values are safe.
        query = 'INSERT INTO passers(name, course_id, campus_id) '
        query += 'VALUES (\'{}\', {}, {})'.format(_escape_string(name),
                                                  course_id,
                                                  campus_id)

        queries.append(query)

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
    _escape_table = [chr(x) for x in range(128)]
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

    print('Scraping records from the UPCAT results site...')
    passers = _scrape_results()

    print('Done!')
    
    if output_type == 'json':
        _write_json(passers)
    elif output_type == 'sql':
        _write_sql(passers)
