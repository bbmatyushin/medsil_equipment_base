function createAkt(aktName) {
	if (!url.searchParams.get(aktName)) url.searchParams.append('akt', aktName);
	location.href = url;
}
const url = new URL(location.href);

var acceptInAktSpan = document.getElementsByClassName('akt-span')[0];
var aktSpan = document.getElementsByClassName('akt-span')[1];
var acceptFromAktSpan = document.getElementsByClassName('akt-span')[2];
acceptInAktSpan.style.padding = '0px 7px 4px 4px';
aktSpan.style.padding = '0px 7px 4px 4px';
acceptFromAktSpan.style.padding = '0px 7px 4px 4px';

var acceptAktButton = document.getElementById('accept-akt-create-btn');
 acceptAktButton.onclick = () => createAkt('acceptInAkt');  // () => нужно, чтобы не вызывалась сразу при загрузке страницы

var acceptAktButton = document.getElementById('accept-akt-from-create-btn');
 acceptAktButton.onclick = () => createAkt('acceptFromAkt');  // () => нужно, чтобы не вызывалась сразу при загрузке страницы

var aktButton = document.getElementById('akt-create-btn');
aktButton.onclick = () => createAkt('serviceAkt');

// Удаляем akt=create из get-параметров, чтобы лишний раз не вызывать метод создания акта в Django 
if (url.searchParams.has('akt')) {
	url.searchParams.delete('akt');
	window.history.replaceState({}, document.title, url.toString());
}