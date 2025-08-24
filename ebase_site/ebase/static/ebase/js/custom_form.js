function createAkt(aktName) {
	if (!url.searchParams.get(aktName)) url.searchParams.append(aktName, 'create');
	location.href = url;
}
const url = new URL(location.href);

var acceptAktSpan = document.getElementsByClassName('akt-span')[0];
var aktSpan = document.getElementsByClassName('akt-span')[1];
acceptAktSpan.style.padding = '0px 7px 4px 4px';
aktSpan.style.padding = '0px 7px 4px 4px';

var acceptAktButton = document.getElementById('accept-akt-create-btn');
// acceptAktButton.onclick = () => createAkt('acceptAkt');  // () => нужно, чтобы не вызывалась сразу при загрузке страницы
acceptAktButton.disabled = true;
acceptAktButton.onclick = () => alert('Акт не загружен.\nАкт приёма-передачи пока не может быть сформирован.');  // () => нужно, чтобы не вызывалась сразу при загрузке страницы

var aktButton = document.getElementById('akt-create-btn');
aktButton.onclick = () => createAkt('akt');

// Удаляем akt=create из get-параметров, чтобы лишний раз не вызывать метод создания акта в Django 
if (url.searchParams.has('akt') || url.searchParams.has('acceptAkt')) {
	url.searchParams.delete('akt');	
	url.searchParams.delete('acceptAkt');
	window.history.replaceState({}, document.title, url.toString());
}