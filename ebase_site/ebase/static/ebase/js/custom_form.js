function createAkt() {
	if (!url.searchParams.get('akt')) url.searchParams.append('akt', 'create');
	location.href = url;
}

// Нужно всё одну функцию упаковать - createAkt
function createAcceptAkt() {
    console.log('createAcceptAkt');
	if (!url.searchParams.get('acceptAkt')) url.searchParams.append('acceptAkt', 'create');
	location.href = url;
}

const url = new URL(location.href);

var acceptAktSpan = document.getElementsByClassName('akt-span')[0];
var aktSpan = document.getElementsByClassName('akt-span')[1];
acceptAktSpan.style.padding = '0px 7px 4px 4px';
aktSpan.style.padding = '0px 7px 4px 4px';

var aktButton = document.getElementById('accept-akt-create-btn');
aktButton.onclick = createAcceptAkt;

var aktButton = document.getElementById('akt-create-btn');
aktButton.onclick = createAkt;

// Удаляем akt=create из get-параметров, чтобы лишний раз не вызывать метод создания акта в Django 
if (url.searchParams.get('akt')) {
	url.searchParams.delete('akt');	
	window.history.replaceState({}, document.title, url.toString());
}