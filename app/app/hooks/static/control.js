const boxcolor = document.querySelector( "#boxcolor" );
const fontcolor = document.getElementById( "fontcolor" );
const textbg = document.getElementById( "textbg" );
const text = document.getElementById( "text" );

boxcolor.addEventListener( "input", function () {
    textbg.style.background = boxcolor.value;
});
fontcolor.addEventListener( "input", function () {
    text.style.color = fontcolor.value;
});