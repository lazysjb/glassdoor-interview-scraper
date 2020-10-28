import time
import json

import Review
import click
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
# from selenium.webdriver.common.keys import Keys

from config import COMPANY_NAME_TO_BASE_URL, USER_SECRETS


# Manual options for the company, num pages to scrape, and URL
pages = 200

def obj_dict(obj):
	return vars(obj)
    # return obj.__dict__
#enddef

def json_export(data, company_name):
	jsonFile = open(company_name + ".json", "w")
	serialized_data = [vars(x) for x in data]

	# jsonFile.write(json.dumps(data, indent=4, separators=(',', ': '), default=obj_dict))
	jsonFile.write(json.dumps(serialized_data, indent=4, separators=(',', ': ')))
	jsonFile.close()
#enddef

def init_driver():
	options = webdriver.ChromeOptions()
	options.add_argument('--ignore-certificate-errors')
	options.add_argument("--test-type")
	# options.binary_location = "./chromedriver"
	driver = webdriver.Chrome(executable_path = "./chromedriver", chrome_options=options)
	# driver.get('https://python.org')

	# driver = webdriver.Chrome(executable_path = "./chromedriver")
	driver.wait = WebDriverWait(driver, 10)
	return driver
#enddef

def login(driver, username, password):
	driver.get("http://www.glassdoor.com/profile/login_input.htm")
	try:
		user_field = driver.wait.until(EC.presence_of_element_located(
			(By.NAME, "username")))
		pw_field = driver.find_element_by_name('password')

		# pw_field = driver.find_element_by_class_name("signin-password")
		login_button = driver.find_element_by_xpath('//button[@type="submit"]')

		# login_button = driver.find_element_by_id("signInBtn")
		user_field.send_keys(username)
		# user_field.send_keys(Keys.TAB)
		time.sleep(1)
		pw_field.send_keys(password)
		time.sleep(1)
		login_button.click()
	except TimeoutException:
		print("TimeoutException! Username/password field or login button not found on glassdoor.com")
#enddef

def parse_reviews_HTML(reviews, data):
	for review in reviews:
		length = "-"
		gotOffer = "-"
		experience = "-"
		difficulty = "-"

		date_node = review.find("time", { "class" : "date" })
		if date_node is None:
			date = 'NA'
		else:
			date = date_node.getText().strip()
		# date = review.find("time", { "class" : "date" }).getText().strip()
		role = review.find("span", { "class" : "reviewer"}).getText().strip()
		outcomes = review.find_all("div", { "class" : ["tightLt", "col"] })
		if (len(outcomes) > 0):
			gotOffer = outcomes[0].find("span", { "class" : "middle"}).getText().strip()
		#endif
		if (len(outcomes) > 1):
			experience = outcomes[1].find("span", { "class" : "middle"}).getText().strip()
		#endif
		if (len(outcomes) > 2):
			difficulty = outcomes[2].find("span", { "class" : "middle"}).getText().strip()
		#endif
		appDetails = review.find("p", { "class" : "applicationDetails"})
		if (appDetails):
			appDetails = appDetails.getText().strip()
			tookFormat = appDetails.find("took ")
			if (tookFormat >= 0):
				start = appDetails.find("took ") + 5
				length = appDetails[start :].split('.', 1)[0]
			#endif
		else:
			appDetails = "-"
		#endif
		details = review.find("p", { "class" : "interviewDetails"})
		if (details):
			s = details.find("span", { "class" : ["link", "moreLink"] })
			if (s):
				s.extract() # Remove the "Show More" text and link if it exists
			#endif
			details = details.getText().strip()
		#endif
		questions = []
		qs = review.find_all("span", { "class" : "interviewQuestion"})
		if (qs):
			for q in qs:
				s = q.find("span", { "class" : ["link", "moreLink"] })
				if (s):
					s.extract() # Remove the "Show More" text and link if it exists
				#endif
				questions.append(q.getText().strip())
				# questions.append(q.getText().encode('utf-8').strip())
			#endfor
		#endif
		r = Review.Review(date, role, gotOffer, experience, difficulty, length, details, questions)
		data.append(r)
	#endfor
	return data
#enddef

def _get_pagenated_url(base_url, pagestr):
	base = base_url.replace('.htm', '')
	pagenated_url = base + "_P" + str(pagestr) + ".htm"
	return pagenated_url


def get_data(driver, URL, startPage, endPage, data, refresh):
	if (startPage > endPage):
		return data
	#endif
	print("\nPage " + str(startPage) + " of " + str(endPage))
	# currentURL = URL + "_IP" + str(startPage) + ".htm"
	currentURL = _get_pagenated_url(URL, str(startPage))
	time.sleep(5)
	#endif
	if (refresh):
		driver.get(currentURL)
		print("Getting " + currentURL)

	#endif
	time.sleep(5)
	HTML = driver.page_source
	soup = BeautifulSoup(HTML, "html.parser")
	nextpage_node = soup.find(attrs={'class': 'pagingControls'}).find(attrs={'class': 'next'}).find('a')

	reviews = soup.find_all("li", { "class" : ["empReview", "padVert"] })
	if (reviews):
		data = parse_reviews_HTML(reviews, data)
		print("Page " + str(startPage) + " scraped.")

		if nextpage_node is None:
			print('Reached last page: {}'.format(currentURL))
			return data

		if (startPage % 10 == 0):
			print("\nTaking a breather for a few seconds ...")
			time.sleep(12)
		#endif
		get_data(driver, URL, startPage + 1, endPage, data, True)
	else:
		print("Waiting ... page still loading or CAPTCHA input required")
		time.sleep(3)
		get_data(driver, URL, startPage, endPage, data, False)
	#endif
	return data
#enddef


def _extract_company_name_map_for_alias(company_alias):
	if company_alias == 'all':
		name_map = COMPANY_NAME_TO_BASE_URL
	else:
		name_map = {}
		name_map[company_alias] = COMPANY_NAME_TO_BASE_URL[company_alias]
	return name_map


@click.command()
@click.option('--company_names', default='all')
def main(company_names):
	driver = init_driver()
	time.sleep(5)
	print("Logging into Glassdoor account ...")
	login(driver, USER_SECRETS['username'], USER_SECRETS['password'])
	time.sleep(5)
	print("\nStarting data scraping ...")

	company_name_map = _extract_company_name_map_for_alias(company_names)

	for company_name, company_url in company_name_map.items():
		data = get_data(driver, company_url, 1, pages, [], True)
		# data = get_data(driver, companyURL[:-4], 1, pages, [], True)
		print("\nExporting data to " + company_name + ".json")
		json_export(data, company_name)

	driver.quit()


if __name__ == "__main__":
	main()
#endif
