/*
code/javascript
*/

rule code_javascript_1 {
    meta:
        type = "code/javascript"

    strings:
        $script = "<script" nocase
        $lang_js1 = "language=\"javascript\"" nocase
        $lang_js2 = "language=\"jscript\"" nocase
        $lang_js3 = "language=\"js\"" nocase
        $lang_js4 = "type=\"text/javascript\"" nocase

    condition:
        $script
        and 1 of ($lang*)
}

rule code_javascript_2 {
    meta:
        type = "code/javascript"

    strings:
        $strong_js1 = /function([ \t]*|[ \t]+[\w|_]+[ \t]*)\([\w_ \t,]*\)[ \t\n\r]*{/
        $strong_js2 = /\beval[ \t]*\("/
        $strong_js3 = /new[ \t]+ActiveXObject\("/
        $strong_js4 = /xfa\.((resolve|create)Node|datasets|form)"/
        $strong_js5 = /\.oneOfChild"/
        $strong_js6 = /unescape\(/
        $strong_js7 = /\.createElement\(/
        $strong_js8 = /submitForm\("/
        $strong_js9 = /document\.write\(/
        $strong_js10 = /setTimeout\(/

        $weak_js1 = /var /
        $weak_js2 = /String\.(fromCharCode|raw)\(/
        $weak_js3 = /Math\.(round|pow|sin|cos)\(/
        $weak_js4 = /(isNaN|isFinite|parseInt|parseFloat)\(/
        $weak_js5 = /WSH/
        $weak_js6 = /(document|window)\[/
        $weak_js7 = /([^\w]|^)this\.[\w]+/

    condition:
        2 of ($strong_js*)
        or (1 of ($strong_js*)
            and 2 of ($weak_js*))
}

/*
code/jscript
*/

rule code_jscript {

    meta:
        type = "code/jscript"
        score = 5

    strings:
        $jscript1 = /new[ \t]+ActiveXObject\(/
        $jscript2 = /Scripting\.Dictionary"/

    condition:
        1 of (code_javascript*)
        and 1 of ($jscript*)
}

/*
code/pdfjs
*/

rule code_pdfjs {

    meta:
        type = "code/pdfjs"
        score = 5

    strings:
        $pdfjs1 = /xfa\.((resolve|create)Node|datasets|form)/
        $pdfjs2 = /\.oneOfChild"/

    condition:
        1 of (code_javascript*)
        and 1 of ($pdfjs*)
}

/*
code/vbs
*/

rule code_vbs {

    meta:
        type = "code/vbs"

    strings:
        $strong_vbs1 = /(^|\n)On[ \t]+Error[ \t]+Resume[ \t]+Next/
        $strong_vbs2 = /(^|\n)(Private)?[ \t]*Sub[ \t]+\w+\(*/
        $strong_vbs3 = /(^|\n)End[ \t]+Module/
        $strong_vbs4 = /(^|\n)ExecuteGlobal/
        $strong_vbs5 = /(^|\n)REM[ \t]+/
        $strong_vbs6 = "ubound(" nocase
        $strong_vbs7 = "CreateObject(" nocase
        $strong_vbs8 = /\.Run[ \t]+\w+,\d(,(False|True))?/
        $strong_vbs9 = /replace\(([\"']?.+[\"']?,){2}([\"']?.+[\"']?)\)/
        $strong_vbs10 = "lbound(" nocase

        $weak_vbs1 = /(^|\n)[ \t]{0,1000}((Dim|Sub|Loop|Attribute|Function|End[ \t]+Function)[ \t]+)|(End[ \t]+Sub)/i
        $weak_vbs2 = "CreateObject" wide ascii nocase
        $weak_vbs3 = "WScript" wide ascii nocase
        $weak_vbs4 = "window_onload" wide ascii nocase
        $weak_vbs5 = ".SpawnInstance_" wide ascii nocase
        $weak_vbs6 = ".Security_" wide ascii nocase
        $weak_vbs7 = "WSH" wide ascii nocase
        $weak_vbs8 = /Set[ \t]+\w+[ \t]*=/i

    condition:
        2 of ($strong_vbs*)
        or (1 of ($strong_vbs*)
            and 2 of ($weak_vbs*))
}

/*
code/html
*/

rule code_html {

    meta:
        type = "code/html"

    strings:
        $html_doctype = "<!doctype html>" nocase
        $html_start = "<html" nocase
        $html_end = "</html" nocase

    condition:
        $html_doctype in (0..256)
        or $html_start in (0..256)
        or $html_end in (filesize-256..filesize)
}

/*
code/html
*/

rule code_hta {

    meta:
        type = "code/hta"
        score = 10

    strings:
        $hta = "<hta:application " nocase

    condition:
        $hta
}

rule code_html_with_script {

    meta:
        type = "code/hta"
        score = 10

    strings:
        $script = "<script" nocase
        $lang_js1 = "language=\"javascript\"" nocase
        $lang_js2 = "language=\"jscript\"" nocase
        $lang_js3 = "language=\"js\"" nocase
        $lang_vbs1 = "language=\"vbscript\"" nocase
        $lang_vbs2 = "language=\"vb\"" nocase

    condition:
        code_html
        and $script
        and 1 of ($lang*)
}

rule code_html_with_js {

    meta:
        type = "code/hta"
        score = 10

    condition:
        code_html and (1 of (code_javascript*) or 1 of (code_vbs*))
}

/*
code/htc
*/

rule code_htc {

    meta:
        type = "code/htc"
        score = 15

    strings:
        $component1 = "public:component " nocase
        $component2 = "/public:component" nocase
        $script = "<script" nocase
        $lang_js1 = "language=\"javascript\"" nocase
        $lang_js2 = "language=\"jscript\"" nocase
        $lang_js3 = "language=\"js\"" nocase
        $lang_vbs1 = "language=\"vbscript\"" nocase
        $lang_vbs2 = "language=\"vb\"" nocase

    condition:
        all of ($component*)
        and $script
        and 1 of ($lang*)
}

/*
document/email
*/

rule document_email_1 {

    meta:
        type = "document/email"
        score = 15

    strings:
        $rec = "From: "
        $rec2 = "Date: "
        $subrec1 = "Bcc: "
        $subrec2 = "To: "
        $opt1 = "Subject: "
        $opt2 = "Received: from"
        $opt3 = "MIME-Version: "
        $opt4 = "Content-Type: "

    condition:
        all of ($rec*)
        and 1 of ($subrec*)
        and 1 of ($opt*)
}

rule document_email_2 {

    meta:
        type = "document/email"
        score = 10

    strings:
        $ = "MIME-Version: "
        $ = "Content-Type: "
        $ = "This is a multipart message in MIME format."

    condition:
        all of them
}
