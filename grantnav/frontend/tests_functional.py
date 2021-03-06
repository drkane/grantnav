import os
import time
import pytest
from dataload.import_to_elasticsearch import import_to_elasticsearch
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import requests

prefix = 'https://raw.githubusercontent.com/OpenDataServices/grantnav-sampledata/560a8d9f21a069a9d51468850188f34ae72a0ec3/'


BROWSER = os.environ.get('BROWSER', 'ChromeHeadless')


@pytest.fixture(scope="module")
def browser(request):
    if BROWSER == 'ChromeHeadless':
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        browser = webdriver.Chrome(chrome_options=chrome_options)
    elif BROWSER == "Firefox":
        # Make downloads work
        profile = webdriver.FirefoxProfile()
        profile.set_preference("browser.download.folderList", 2)
        profile.set_preference("browser.download.manager.showWhenStarting", False)
        profile.set_preference("browser.download.dir", os.getcwd())
        profile.set_preference("browser.helperApps.neverAsk.saveToDisk", "application/json")
        browser = getattr(webdriver, BROWSER)(firefox_profile=profile)
    else:
        browser = getattr(webdriver, BROWSER)()
    browser.implicitly_wait(3)
    request.addfinalizer(lambda: browser.quit())
    return browser


@pytest.fixture(scope="module")
def server_url(request, live_server):
    if 'CUSTOM_SERVER_URL' in os.environ:
        return os.environ['CUSTOM_SERVER_URL']
    else:
        return live_server.url


@pytest.fixture(scope="module")
def dataload():
    import_to_elasticsearch([prefix + 'a002400000KeYdsAAF.json',
                             prefix + 'a002400000OiDBQAA3.xlsx',
                             prefix + 'a002400000G4KGJAA3.csv'], clean=True)
    #elastic search needs some time to commit its data
    time.sleep(2)


@pytest.fixture(scope="function")
def provenance_dataload(dataload, settings, tmpdir):
    local_data_json = tmpdir.join('data.json')
    local_data_json.write(requests.get(prefix + 'data.json').content)
    settings.PROVENANCE_JSON = local_data_json.strpath


def test_home(provenance_dataload, server_url, browser):
    browser.get(server_url)
    assert 'GrantNav' in browser.find_element_by_tag_name('body').text

    assert 'Cookies disclaimer' in browser.find_element_by_id('CookielawBanner').text
    browser.find_element_by_class_name("btn").click()
    browser.get(server_url)
    assert 'Cookies disclaimer' not in browser.find_element_by_tag_name('body').text
    assert '360Giving Standard' in browser.find_element_by_tag_name('body').text
    assert '360Giving standard' not in browser.find_element_by_tag_name('body').text


@pytest.mark.parametrize(('link_text'), [
    ('About'),
    ('Funders'),
    ('Recipients'),
    ('Help with Using GrantNav'),
    ('Terms and Conditions'),
    ('Take Down Policy'),
    ('Data Used in GrantNav'),
    ('Reusing GrantNav Data'),
    ('Copyright'),
    ('Developers')
    ])
def test_footer_links(provenance_dataload, server_url, browser, link_text):
    browser.get(server_url)
    browser.find_element_by_link_text(link_text)
    

@pytest.mark.parametrize(('text'), [
    ('Contains OS data © Crown copyright and database right 2016'),
    ('Contains Royal Mail data © Royal Mail copyright and Database right 2016'),
    ('Contains National Statistics data © Crown copyright and database right 2015 & 2016')
    ])
def test_code_point_credit(provenance_dataload, server_url, browser, text):
    browser.get(server_url)
    browser.find_element_by_link_text('Copyright').click()
    assert text in browser.find_element_by_tag_name('body').text


def test_search(provenance_dataload, server_url, browser):
    browser.get(server_url)
    browser.find_element_by_class_name("large-search-icon").click()
    assert '4,764' in browser.find_element_by_tag_name('body').text
    assert 'Lloyds Bank Foundation for England and Wales (4,116)' in browser.find_element_by_tag_name('body').text
    assert 'Wolfson Foundation (379)' in browser.find_element_by_tag_name('body').text
    other_currencies_modal = browser.find_element_by_id("other-currencies-modal")
    assert other_currencies_modal.text == '7'
    other_currencies_modal.click()
    time.sleep(0.5)
    assert "$146,325" in browser.find_element_by_tag_name('body').text


def test_bad_search(provenance_dataload, server_url, browser):
    browser.get(server_url)
    browser.find_element_by_name("text_query").send_keys(" £s:::::afdsfas")
    browser.find_element_by_class_name("large-search-icon").click()
    not_valid = browser.find_element_by_id('not_valid').text
    assert 'Search input is not valid' in not_valid
    assert "We can't find what you tried to search for." in not_valid
    assert "Filter By" in browser.find_element_by_tag_name('h3').text


def test_terms(server_url, browser):
    browser.get(server_url + '/terms')
    assert 'Terms and conditions' in browser.find_element_by_tag_name('h1').text


def test_take_down(server_url, browser):
    browser.get(server_url + '/take_down_policy')
    assert 'Take Down Policy' in browser.find_element_by_tag_name('h1').text


def test_help_page(server_url, browser):
    browser.get(server_url + '/help')
    assert 'Using GrantNav' in browser.find_element_by_tag_name('h1').text


def test_developers(server_url, browser):
    browser.get(server_url + '/developers')
    assert 'developers' in browser.find_element_by_tag_name('h1').text


def test_title(server_url, browser):
    browser.get(server_url)
    assert '360Giving GrantNav' in browser.title


def test_no_results_page(server_url, browser):
    # thanks: http://stackoverflow.com/questions/18557275/locating-entering-a-value-in-a-text-box-using-selenium-and-python
    browser.get(server_url)
    inputElement = browser.find_element_by_css_selector(".large-search")
    inputElement.send_keys('dfsergegrdtytdrthgrtyh')
    inputElement.submit()
    no_results = browser.find_element_by_id('no-results').text
    assert 'No Results' in no_results
    assert 'Your search - "dfsergegrdtytdrthgrtyh" - did not match any records.' in no_results
    assert "Filter By" in browser.find_element_by_tag_name('h3').text


@pytest.mark.parametrize(('path'), [
    ('/funder/GB-CHC-327114'),  # funder: Lloyds
    #('/region/South West'),  # region
    ('/recipient/GB-CHC-1092728'),  # recipient: Open Doors
    #('/district/City of Bristol')  # district
    ])
def test_right_align_amounts_in_grant_table(provenance_dataload, server_url, browser, path):
    browser.get(server_url + path)
    grants_table = browser.find_element_by_id('grants_datatable')
    grants_table.find_element_by_css_selector('td.amount')


@pytest.mark.parametrize(('path', 'identifier'), [
    ('/funders', 'funders_datatable'),
    ('/recipients', 'recipients_datatable'),
    ('/funder/GB-CHC-327114', 'recipients_datatable'),  # funder: Lloyds
    ])
def test_right_align_amounts_in_other_tables(provenance_dataload, server_url, browser, path, identifier):
    browser.get(server_url + path)
    table = browser.find_element_by_id(identifier)
    table.find_elements_by_css_selector('td.amount')


def test_datasets_page(server_url, browser):
    browser.get(server_url + '/datasets')
    assert 'Data used in GrantNav' in browser.find_element_by_tag_name('h1').text


@pytest.mark.parametrize(('path', 'identifier', 'text'), [
    ('/funder/GB-CHC-327114', 'disclaimer', 'This data is provided for information purposes only.'),
    ('/funder/GB-CHC-327114', 'disclaimer', 'Please refer to the funder website for details of current grant programmes, application guidelines and eligibility criteria.'),
    ('/grant/360G-LBFEW-111657', 'provenance', 'Where is this data from?'),
    ('/grant/360G-LBFEW-111657', 'provenance', 'This data was originally published by')
    ])
def test_disclaimers(server_url, browser, path, identifier, text):
    browser.get(server_url + path)
    assert text in browser.find_element_by_id(identifier).text


def test_currency_facet(provenance_dataload, server_url, browser):
    browser.get(server_url)
    browser.find_element_by_class_name("large-search-icon").click()
    browser.find_element_by_link_text("USD (4)").click()
    assert 'USD 0 - USD 500' in browser.find_element_by_tag_name('body').text
