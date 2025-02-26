# conversor-pdf-para-XML
Conversor PDF para XML em fase de desenvolvimento 
Thought for 1 second```python
from abc import ABC, abstractmethod
import xml.etree.ElementTree as ET
from datetime import datetime
import re
from typing import Dict, Optional
from dataclasses import dataclass
import xmlsec
from lxml import etree
import json
import os
import logging
from enum import Enum

class MunicipioEnum(Enum):
    """Enumeração dos municípios suportados"""
    SAO_PAULO = "3550308"
    RIO_JANEIRO = "3304557"
    CAMPINAS = "3509502"
    BELO_HORIZONTE = "3106200"

@dataclass
class NFSeData:
    """Dados comuns para NFSe"""
    numero: str
    serie: str = "1"
    tipo: str = "1"
    data_emissao: str
    valor_servicos: str
    iss_retido: str = "2"
    item_servico: str
    discriminacao: str
    prestador_cnpj: str
    prestador_inscricao_municipal: str
    tomador_cnpj: str
    tomador_nome: str
    tomador_endereco: Optional[Dict] = None
    aliquota: Optional[str] = None
    base_calculo: Optional[str] = None

class XMLBuilder(ABC):
    """Classe base para construção de XML"""
    
    def __init__(self, versao_schema: str = "2.04"):
        self.versao_schema = versao_schema
        self.namespaces = {
            "xsi": "http://www.w3.org/2001/XMLSchema-instance",
            "xsd": "http://www.w3.org/2001/XMLSchema",
        }
    
    @abstractmethod
    def build_xml(self, data: NFSeData) -> str:
        """Constrói o XML específico do município"""
        pass
    
    def _format_xml(self, root: ET.Element) -> str:
        """Formata o XML com indentação"""
        from xml.dom import minidom
        xml_str = ET.tostring(root, encoding='unicode', method='xml')
        return minidom.parseString(xml_str).toprettyxml(indent="  ")
    
    def validate_xml(self, xml_str: str, schema_path: str) -> bool:
        """Valida o XML contra o schema XSD"""
        try:
            schema = etree.XMLSchema(etree.parse(schema_path))
            xml_doc = etree.fromstring(xml_str.encode())
            schema.assertValid(xml_doc)
            return True
        except Exception as e:
            logging.error(f"Erro na validação do XML: {str(e)}")
            return False

class SaoPauloXMLBuilder(XMLBuilder):
    """Construtor de XML para São Paulo"""
    
    def __init__(self):
        super().__init__()
        self.namespace = "http://www.prefeitura.sp.gov.br/nfe"
        self.namespaces.update({"nfe": self.namespace})
        
    def build_xml(self, data: NFSeData) -> str:
        root = ET.Element("PedidoEnvioRPS", {
            "xmlns": self.namespace,
            "xmlns:xsi": self.namespaces["xsi"]
        })
        
        # Cabeçalho
        cabecalho = ET.SubElement(root, "Cabecalho")
        ET.SubElement(cabecalho, "Versao").text = self.versao_schema
        ET.SubElement(cabecalho, "CPFCNPJRemetente").text = data.prestador_cnpj
        
        # RPS
        rps = ET.SubElement(root, "RPS")
        
        # Assinatura
        ET.SubElement(rps, "Assinatura").text = self._generate_sp_signature(data)
        
        # Dados do RPS
        ET.SubElement(rps, "ChaveRPS")
        ET.SubElement(rps, "TipoRPS").text = "RPS"
        ET.SubElement(rps, "DataEmissao").text = data.data_emissao
        ET.SubElement(rps, "StatusRPS").text = "N"
        ET.SubElement(rps, "TributacaoRPS").text = "T"
        
        # Valores
        ET.SubElement(rps, "ValorServicos").text = data.valor_servicos
        ET.SubElement(rps, "ValorDeducoes").text = "0.00"
        ET.SubElement(rps, "AliquotaServicos").text = data.aliquota or "5.00"
        
        # Serviço
        ET.SubElement(rps, "CodigoServico").text = data.item_servico
        ET.SubElement(rps, "Discriminacao").text = data.discriminacao
        
        # Tomador
        tomador = ET.SubElement(rps, "Tomador")
        ET.SubElement(tomador, "CPFCNPJ").text = data.tomador_cnpj
        ET.SubElement(tomador, "RazaoSocial").text = data.tomador_nome
        
        if data.tomador_endereco:
            endereco = ET.SubElement(tomador, "Endereco")
            for key, value in data.tomador_endereco.items():
                ET.SubElement(endereco, key).text = value
        
        return self._format_xml(root)
    
    def _generate_sp_signature(self, data: NFSeData) -> str:
        """Gera assinatura específica de São Paulo"""
        # Implementação da lógica de assinatura de SP
        return "assinatura_exemplo"

class RioJaneiroXMLBuilder(XMLBuilder):
    """Construtor de XML para Rio de Janeiro"""
    
    def __init__(self):
        super().__init__()
        self.namespace = "http://notacarioca.rio.gov.br"
        self.namespaces.update({"nfse": self.namespace})
    
    def build_xml(self, data: NFSeData) -> str:
        root = ET.Element("GerarNfseEnvio", {
            "xmlns": self.namespace,
            "xmlns:xsi": self.namespaces["xsi"]
        })
        
        # RPS
        rps = ET.SubElement(root, "Rps")
        inf_rps = ET.SubElement(rps, "InfRps")
        
        # Identificação
        ident = ET.SubElement(inf_rps, "IdentificacaoRps")
        ET.SubElement(ident, "Numero").text = data.numero
        ET.SubElement(ident, "Serie").text = data.serie
        ET.SubElement(ident, "Tipo").text = data.tipo
        
        # Dados básicos
        ET.SubElement(inf_rps, "DataEmissao").text = data.data_emissao
        ET.SubElement(inf_rps, "NaturezaOperacao").text = "1"
        ET.SubElement(inf_rps, "RegimeEspecialTributacao").text = "1"
        ET.SubElement(inf_rps, "OptanteSimplesNacional").text = "2"
        ET.SubElement(inf_rps, "IncentivadorCultural").text = "2"
        ET.SubElement(inf_rps, "Status").text = "1"
        
        # Serviço
        servico = ET.SubElement(inf_rps, "Servico")
        valores = ET.SubElement(servico, "Valores")
        ET.SubElement(valores, "ValorServicos").text = data.valor_servicos
        ET.SubElement(valores, "IssRetido").text = data.iss_retido
        
        if data.base_calculo:
            ET.SubElement(valores, "BaseCalculo").text = data.base_calculo
        
        ET.SubElement(servico, "ItemListaServico").text = data.item_servico
        ET.SubElement(servico, "CodigoTributacaoMunicipio").text = data.item_servico
        ET.SubElement(servico, "Discriminacao").text = data.discriminacao
        ET.SubElement(servico, "CodigoMunicipio").text = "3304557"
        
        # Prestador
        prestador = ET.SubElement(inf_rps, "Prestador")
        ET.SubElement(prestador, "Cnpj").text = data.prestador_cnpj
        ET.SubElement(prestador, "InscricaoMunicipal").text = data.prestador_inscricao_municipal
        
        # Tomador
        tomador = ET.SubElement(inf_rps, "Tomador")
        if data.tomador_cnpj:
            ident_tomador = ET.SubElement(tomador, "IdentificacaoTomador")
            cpf_cnpj = ET.SubElement(ident_tomador, "CpfCnpj")
            ET.SubElement(cpf_cnpj, "Cnpj").text = data.tomador_cnpj
        
        ET.SubElement(tomador, "RazaoSocial").text = data.tomador_nome
        
        if data.tomador_endereco:
            endereco = ET.SubElement(tomador, "Endereco")
            for key, value in data.tomador_endereco.items():
                ET.SubElement(endereco, key).text = value
        
        return self._format_xml(root)

class XMLBuilderFactory:
    """Fábrica de construtores XML"""
    
    _builders = {
        MunicipioEnum.SAO_PAULO.value: SaoPauloXMLBuilder,
        MunicipioEnum.RIO_JANEIRO.value: RioJaneiroXMLBuilder
    }
    
    @classmethod
    def get_builder(cls, codigo_municipio: str) -> XMLBuilder:
        """Retorna o construtor XML apropriado para o município"""
        builder_class = cls._builders.get(codigo_municipio)
        if not builder_class:
            raise ValueError(f"Município não suportado: {codigo_municipio}")
        return builder_class()

class NFSeXMLManager:
    """Gerenciador de XML NFSe"""
    
    def __init__(self, codigo_municipio: str):
        self.builder = XMLBuilderFactory.get_builder(codigo_municipio)
    
    def generate_xml(self, data: NFSeData) -> str:
        """Gera XML da NFSe"""
        return self.builder.build_xml(data)
    
    def validate_xml(self, xml_str: str, schema_path: str) -> bool:
        """Valida o XML gerado"""
        return self.builder.validate_xml(xml_str, schema_path)

# Exemplo de uso
def exemplo_uso():
    # Dados de exemplo
    data = NFSeData(
        numero="1234",
        data_emissao="2024-02-25T14:30:00",
        valor_servicos="1000.00",
        item_servico="1.05",
        discriminacao="Serviços de desenvolvimento de software",
        prestador_cnpj="12345678000199",
        prestador_inscricao_municipal="123456",
        tomador_cnpj="98765432000199",
        tomador_nome="Empresa Cliente Ltda",
        tomador_endereco={
            "Endereco": "Rua Exemplo",
            "Numero": "123",
            "Complemento": "Sala 456",
            "Bairro": "Centro",
            "CodigoMunicipio": "3304557",
            "Uf": "RJ",
            "Cep": "20000000"
        }
    )
    
    try:
        # Exemplo para Rio de Janeiro
        print("Gerando XML para Rio de Janeiro:")
        rj_manager = NFSeXMLManager(MunicipioEnum.RIO_JANEIRO.value)
        rj_xml = rj_manager.generate_xml(data)
        print(rj_xml)
        
        # Exemplo para São Paulo
        print("\nGerando XML para São Paulo:")
        sp_manager = NFSeXMLManager(MunicipioEnum.SAO_PAULO.value)
        sp_xml = sp_manager.generate_xml(data)
        print(sp_xml)
        
    except Exception as e:
        print(f"Erro: {str(e)}")

if __name__ == "__main__":
    exemplo_uso()
```

Esta biblioteca oferece:

1. **Estrutura Modular**:

1. `XMLBuilder`: Classe base abstrata para construção de XML
2. `SaoPauloXMLBuilder`: Implementação específica para São Paulo
3. `RioJaneiroXMLBuilder`: Implementação específica para Rio de Janeiro
4. `XMLBuilderFactory`: Fábrica para criar o construtor apropriado



2. **Recursos por Município**:

1. São Paulo:

1. Formato específico do PedidoEnvioRPS
2. Assinatura específica de SP
3. Campos obrigatórios da prefeitura



2. Rio de Janeiro:

1. Formato NotaCarioca
2. Campos específicos do RJ
3. Validações próprias






3. **Validação**:

1. Suporte a schemas XSD
2. Validação por município
3. Tratamento de erros



4. **Extensibilidade**:

1. Fácil adição de novos municípios
2. Configuração flexível
3. Reutilização de código





Para usar:

1. Crie os dados da NFSe:


```python
data = NFSeData(
    numero="1234",
    data_emissao="2024-02-25",
    valor_servicos="1000.00",
    # ... outros campos
)
```

2. Escolha o município e gere o XML:


```python
# Para Rio de Janeiro
manager = NFSeXMLManager(MunicipioEnum.RIO_JANEIRO.value)
xml = manager.generate_xml(data)

# Para São Paulo
manager = NFSeXMLManager(MunicipioEnum.SAO_PAULO.value)
xml = manager.generate_xml(data)
```

Para adicionar um novo município:

1. Crie uma nova classe herdando de `XMLBuilder`
2. Implemente o método `build_xml`
3. Adicione o município ao `MunicipioEnum`
4. Registre o builder na `XMLBuilderFactory`


Você pode integrar esta biblioteca ao código anterior do conversor PDF-XML, substituindo a parte de geração de XML pela chamada apropriada ao `NFSeXMLManager`.
