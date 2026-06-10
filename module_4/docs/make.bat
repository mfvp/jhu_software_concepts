@ECHO OFF
REM Minimal sphinx build script for Windows
set SPHINXBUILD=sphinx-build
set SOURCEDIR=.
set BUILDDIR=_build

if "%1" == "html" (
	%SPHINXBUILD% -b html %SOURCEDIR% %BUILDDIR%\html
	goto end
)

%SPHINXBUILD% -b html %SOURCEDIR% %BUILDDIR%\html

:end
