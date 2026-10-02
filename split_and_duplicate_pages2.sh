#!/bin/bash

# Controlla che il file PDF sia passato come argomento
if [ -z "$1" ]; then
  echo "Errore: devi fornire il file PDF come argomento."
  exit 1
fi

# Verifica se il file esiste
if [ ! -f "$1" ]; then
  echo "Errore: il file $1 non esiste."
  exit 1
fi

# Ottieni il nome del file senza l'estensione
filename=$(basename -- "$1")
filename_noext="${filename%.*}"

# Crea una cartella con il nome del file PDF
mkdir "$filename_noext"

# Estrai il numero totale di pagine del PDF
total_pages=$(pdfinfo "$1" | grep "Pages:" | awk '{print $2}')

pdftk "$1" burst output "$filename_noext/page_%03d.pdf"

# cicla tutti i file del tipo page_*.pdf nella directory e duplica le pagine .

cd "${filename_noext}"

# echo startlogging > mylog.log

for file in ./page_*.pdf; do

  # echo file is $file >> mylog.log
  
  basefile=$(basename -- "$file")
  # echo basefile is $basefile >> mylog.log

  new_file="./${basefile#page_}"
  # echo new_file is $new_file >> mylog.log
  
  # duplica la pagina
  pdftk "${file}" "${file}" cat output "${new_file}"
  rm $file

done

rm "./doc_data.txt"

echo "Processo completato. I file sono stati salvati nella cartella '$filename_noext'."
