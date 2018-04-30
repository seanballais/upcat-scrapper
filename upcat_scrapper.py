import requests
import json
from bs4 import BeautifulSoup


def scrape_page(page_url):
    page = requests.get(page_url)
    soup = BeautifulSoup(page.text, 'html.parser')

    passers = list()
    html_passers_table = soup.find_all('table')[2:3]
    html_passers_tbody = html_passers_table[0].find_all('tbody')[0]
    html_passers_row = html_passers_tbody.find_all('tr')

    num_passers = len(html_passers_row)
    counter = 0
    passers_per_record = 5
    while counter < num_passers:
        # We need to pack a few records into one record because of Algolia's
        # community version limitation.
        records = html_passers_row[counter:counter + passers_per_record]
        names = []
        campuses = []
        courses = []
        for record in records:
            data = record.find_all('td')
            names.append(data[0].text.strip())
            campuses.append(data[1].text.strip())
            courses.append(data[2].text.strip())

        passers.append({
            'name': '|'.join(names),
            'campus': '|'.join(campuses),
            'course': '|'.join(courses)
        })

        counter += passers_per_record

    return passers


def scrape_results(root_url, start, end):
    passers = list()
    for page_count in range(start, end + 1):
        url = '{}/page-{}.html'.format(root_url, str(page_count).zfill(3))
        passers_subset = scrape_page(url)
        passers.extend(passers_subset)

    return passers


if __name__ == '__main__':
    print('Scraping 14k records from the UPCAT results...')
    passers = scrape_results('http://upcat.stickbread.net', 1, 259)
    with open('passers.json', 'w') as passers_file:
        json.dump(passers, passers_file)

    print('Data in "passers.json"...')
