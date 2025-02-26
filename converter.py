import os
import shutil
import time
import PyPDF2
import tkinter as tk
from tkinter import ttk, scrolledtext
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import logging
from threading import Thread
import re

class NFSeConverter:
    def __init__(self):
        self.setup_logging()
        self.folders = self.create_folders()
        self.setup_gui()
        self.observer = None
        self.watching = False

    def setup_logging(self):
        """Configure logging"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('nfse_converter.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)

    def create_folders(self):
        """Create necessary folders"""
        folders = {
            'pdf_input': 'pdf_input',
            'xml_output': 'xml_output',
            'processed_pdf': 'processed_pdf',
            'failed': 'failed',
            'logs': 'logs'
        }
        
        for folder in folders.values():
            if not os.path.exists(folder):
                os.makedirs(folder)
                self.logger.info(f"Created folder: {folder}")
        
        return {name: os.path.abspath(folder) for name, folder in folders.items()}

    def extract_pdf_data(self, pdf_path):
        """Extract data from PDF file"""
        try:
            with open(pdf_path, 'rb') as file:
                reader = PyPDF2.PdfReader(file)
                text = ""
                for page in reader.pages:
                    text += page.extract_text()

            # Extract data using regex patterns
            data = {
                'numero': self.extract_pattern(text, r'Número da Nota: (\d+)'),
                'serie': self.extract_pattern(text, r'Série: (\w+)'),
                'data_emissao': self.extract_pattern(text, r'Data Emissão: (\d{2}/\d{2}/\d{4})'),
                'valor_servicos': self.extract_pattern(text, r'Valor dos Serviços: R\$ ([\d.,]+)'),
                'prestador_cnpj': self.extract_pattern(text, r'CNPJ: (\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})'),
                'descricao': self.extract_pattern(text, r'Descrição dos Serviços:(.*?)(?=\n\n)', flags=re.DOTALL)
            }

            return data

        except Exception as e:
            self.logger.error(f"Error extracting PDF data: {str(e)}")
            raise

    def extract_pattern(self, text, pattern, flags=0):
        """Extract data using regex pattern"""
        match = re.search(pattern, text, flags=flags)
        return match.group(1).strip() if match else ""

    def create_nfse_xml(self, data, file_name):
        """Create NFSe XML with extracted data"""
        root = ET.Element("GerarNfseEnvio", {
            'xmlns': "http://www.abrasf.org.br/nfse.xsd",
            'xmlns:xsi': "http://www.w3.org/2001/XMLSchema-instance"
        })
        
        # Create main structure
        rps = ET.SubElement(root, "Rps")
        inf_declaracao = ET.SubElement(rps, "InfDeclaracaoPrestacaoServico")
        
        # Add RPS data
        rps_id = ET.SubElement(inf_declaracao, "Rps")
        ident_rps = ET.SubElement(rps_id, "IdentificacaoRps")
        ET.SubElement(ident_rps, "Numero").text = data.get('numero', '1')
        ET.SubElement(ident_rps, "Serie").text = data.get('serie', '1')
        ET.SubElement(ident_rps, "Tipo").text = "1"
        
        # Add service data
        servico = ET.SubElement(inf_declaracao, "Servico")
        valores = ET.SubElement(servico, "Valores")
        ET.SubElement(valores, "ValorServicos").text = data.get('valor_servicos', '0.00')
        ET.SubElement(valores, "IssRetido").text = "2"
        ET.SubElement(servico, "ItemListaServico").text = "01.01"
        ET.SubElement(servico, "Discriminacao").text = data.get('descricao', '')
        ET.SubElement(servico, "CodigoMunicipio").text = "3550308"
        
        # Format XML with pretty print
        from xml.dom import minidom
        xml_str = ET.tostring(root, encoding='unicode', method='xml')
        xml_pretty = minidom.parseString(xml_str).toprettyxml(indent="  ")
        
        return xml_pretty

    def convert_pdf_to_nfse_xml(self, pdf_path):
        """Convert PDF to NFSe XML"""
        try:
            self.log_to_gui(f"Processing: {pdf_path}")
            
            # Extract data from PDF
            data = self.extract_pdf_data(pdf_path)
            
            # Get filename without extension
            file_name = Path(pdf_path).stem
            
            # Generate XML
            xml_content = self.create_nfse_xml(data, file_name)
            
            # Save XML file
            xml_path = os.path.join(self.folders['xml_output'], f"{file_name}.xml")
            with open(xml_path, 'w', encoding='utf-8') as f:
                f.write(xml_content)
                
            # Move processed PDF
            processed_pdf_path = os.path.join(self.folders['processed_pdf'], os.path.basename(pdf_path))
            shutil.move(pdf_path, processed_pdf_path)
            
            self.log_to_gui(f"Successfully converted: {pdf_path}")
            self.log_to_gui(f"XML saved to: {xml_path}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error processing {pdf_path}: {str(e)}")
            self.log_to_gui(f"Error processing {pdf_path}: {str(e)}")
            
            # Move failed PDF
            failed_pdf_path = os.path.join(self.folders['failed'], os.path.basename(pdf_path))
            shutil.move(pdf_path, failed_pdf_path)
            
            return False

    def setup_gui(self):
        """Setup GUI interface"""
        self.root = tk.Tk()
        self.root.title("NFSe PDF to XML Converter")
        self.root.geometry("800x600")

        # Create main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Status section
        status_frame = ttk.LabelFrame(main_frame, text="Status", padding="5")
        status_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E))
        
        self.status_label = ttk.Label(status_frame, text="Ready")
        self.status_label.grid(row=0, column=0, sticky=tk.W)

        # Folder monitoring controls
        control_frame = ttk.Frame(main_frame, padding="5")
        control_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E))

        self.watch_button = ttk.Button(control_frame, text="Start Monitoring", command=self.toggle_watch)
        self.watch_button.grid(row=0, column=0, padx=5)

        self.process_button = ttk.Button(control_frame, text="Process Now", command=self.process_existing_files)
        self.process_button.grid(row=0, column=1, padx=5)

        # Log area
        log_frame = ttk.LabelFrame(main_frame, text="Log", padding="5")
        log_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S))

        self.log_text = scrolledtext.ScrolledText(log_frame, height=20)
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Configure grid weights
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(2, weight=1)
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)

    def log_to_gui(self, message):
        """Add message to GUI log"""
        self.log_text.insert(tk.END, f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - {message}\n")
        self.log_text.see(tk.END)
        self.logger.info(message)

    def toggle_watch(self):
        """Toggle folder monitoring"""
        if not self.watching:
            self.start_watching()
            self.watch_button.config(text="Stop Monitoring")
            self.status_label.config(text="Monitoring folder...")
        else:
            self.stop_watching()
            self.watch_button.config(text="Start Monitoring")
            self.status_label.config(text="Monitoring stopped")

    def start_watching(self):
        """Start monitoring input folder"""
        self.watching = True
        event_handler = PDFHandler(self)
        self.observer = Observer()
        self.observer.schedule(event_handler, self.folders['pdf_input'], recursive=False)
        self.observer.start()

    def stop_watching(self):
        """Stop monitoring input folder"""
        self.watching = False
        if self.observer:
            self.observer.stop()
            self.observer.join()

    def process_existing_files(self):
        """Process existing PDF files in input folder"""
        pdf_files = [f for f in os.listdir(self.folders['pdf_input']) 
                    if f.lower().endswith('.pdf')]
        
        if not pdf_files:
            self.log_to_gui("No PDF files found in input folder")
            return
        
        self.log_to_gui(f"Found {len(pdf_files)} PDF files to process")
        
        for pdf_file in pdf_files:
            pdf_path = os.path.join(self.folders['pdf_input'], pdf_file)
            self.convert_pdf_to_nfse_xml(pdf_path)

    def run(self):
        """Start the application"""
        self.root.mainloop()

class PDFHandler(FileSystemEventHandler):
    """Handle PDF file events in the input folder"""
    def __init__(self, converter):
        self.converter = converter

    def on_created(self, event):
        if not event.is_directory and event.src_path.lower().endswith('.pdf'):
            self.converter.log_to_gui(f"New PDF detected: {event.src_path}")
            # Wait a moment to ensure file is completely written
            time.sleep(1)
            self.converter.convert_pdf_to_nfse_xml(event.src_path)

def main():
    converter = NFSeConverter()
    converter.run()

if __name__ == "__main__":
    main()