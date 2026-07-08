import time
import pathlib

import pandas as pd
from fpdf import FPDF
from pypdf import PdfWriter
from matplotlib.backends.backend_pdf import PdfPages

def append_pdf(outdir, pdf1, pdf2, delete = True):
   '''
   Appends pdf2 to the end of pdf1 and deletes pdf2 if requested.
   Output file location is specified by outdir, a Path object
   pdf1 and pdf2 should also be Path objects
   '''
   timestamp = int(time.time())
   temp = outdir / f'{timestamp}.pdf'

   writer = PdfWriter()
   print(pdf1,pdf2)
   writer.append(pdf1)
   writer.append(pdf2)
   with open(temp, "wb") as output_file:
      writer.write(output_file)
   writer.close()

   # Delete pdf1 and rename appended file to have pdf1's old name
   pdf1.unlink()
   temp.rename(pdf1)

   if delete: pdf2.unlink()

def save_to_folder(outdir, root_fname, standard_results, fit_results, logger=None):
   '''
   Saves standard and fit results to a CSV and PDF 
   Parameters:
      outdir - A Path object corresponding to the path from the cwd to the output directory
      root_fname - A string that makes up the root of all saved files
      standard_results - A list of lists containing a header, and individual lines with channel, n_events, duration, and event rate data respectively
      fit_results - A dictionary of lists of FitResult objects whose keys correspond to the fit performed
   '''
   # Initialization
   stan_pdf = FPDF()
   stan_pdf.add_page()
   stan_pdf.set_font("Times", size=12)
   stan_pdf_name = outdir / f'{root_fname}_results.pdf'
   fit_pdf_name = outdir / f'{root_fname}_results_fit.pdf'
   fit_pdf = PdfPages(fit_pdf_name)

   # Save standard results
   ## CSV
   df = pd.DataFrame(standard_results[1:], columns=standard_results[0])
   df.to_csv(outdir / f'{root_fname}_standard_analysis_results.csv', index=False)
   if logger: logger.info(f'Standard results saved to {outdir / f"{root_fname}_standard_analysis_results.csv"}')
   ## PDF
   with stan_pdf.table() as table:
      for data_row in standard_results:
         row = table.row()
         for datum in data_row:
            row.cell(datum)
   stan_pdf.output(stan_pdf_name)

   # Save fit results
   for type, fits in fit_results.items():
      ## CSV
      data = []
      for fit in fits: data.append(fit.result_row)
      df = pd.DataFrame(data)
      df.to_csv(outdir / f'{root_fname}_{type}_fit.csv', index=False)
      if logger: logger.info(f'Fit results saved to {outdir / f"{root_fname}_{type}_fit.csv"}')
      ## PDF
      for fit in fits:
         fit_pdf.savefig(fit.fig)
   fit_pdf.close()

   # Combine PDFs
   append_pdf(outdir, stan_pdf_name, fit_pdf_name)
   if logger: logger.info(f'PDF assembled and saved to {outdir / f"{root_fname}_results"}')