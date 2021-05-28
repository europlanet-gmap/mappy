VERSION=$(shell git describe --tags --abbrev=0)

updateversion:
	sed -i  's/version=[.a-zA-Z0-9]*/version=$(VERSION)/g' mappy/metadata.txt

updateinfo:
	cd scripts; \
	./render_info_to_html.py

update-stuff: updateversion updateinfo
	
deploy: update-stuff
	cd mappy;\
	pb_tool clean -y;\
	pb_tool deploy -y
	
package: update-stuff
	$(info    VERSION:  $(VERSION))
	cd mappy; \
	rm -fr providers/__pycache__;\
	pb_tool clean -y;\
	pb_tool zip; \
	cp zip_build/mappy.zip zip_build/mappy-${VERSION}.zip 


tests:
	cd mappy/tests; \
	pytest -vs --order-dependencies
	

	
