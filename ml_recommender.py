# /epics_recommendation_flask/ml_recommender.py

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import nltk
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
import string
import database as db

try:
    stop_words_es = stopwords.words('spanish')
except LookupError:
    print("ML_DEBUG: Recursos de NLTK 'stopwords' para español no encontrados. Intentando descargar...")
    try:
        nltk.download('stopwords', quiet=True)
        stop_words_es = stopwords.words('spanish')
    except Exception as e:
        print(f"ML_DEBUG: No se pudieron descargar stopwords: {e}. Usando lista vacía.")
        stop_words_es = []

stop_words_es.extend(['experiencia', 'requisitos', 'conocimientos', 'habilidades', 'empresa',
                      'desarrollo', 'trabajo', 'equipo', 'proyecto', 'proyectos', 'años',
                      'buscamos', 'responsabilidades', 'manejo', 'nivel', 'avanzado',
                      'intermedio', 'básico', 'junior', 'senior', 'inglés', 'graduado',
                      'ingeniería', 'sistemas', 'informática', 'afines', 'capacidad',
                      'conocimiento', 'sólida', 'sólidos', 'requiere', 'deseable',
                      'oportunidad', 'importante', 'parte', 'funciones', 'principal',
                      'principales', 'área', 'sector', 'disponibilidad', 'inmediata',
                      'profesional', 'carrera', 'etc', 'mas', 'uso', 'herramientas',
                      'plataforma', 'plataformas', 'tecnologías', 'participación',
                      'desarrollar', 'trabajar', 'colaborar', 'diseñar', 'implementar',
                      'optimizar', 'análisis', 'datos', 'gestión', 'busco', 'roles',
                      'interesado', 'abierto', 'remoto', 'híbrido', 'presencial', 'lima',
                      'perú', 'salario', 'bruto', 'mensual', 'anual', 'contrato', 'indefinido',
                      'temporal', 'prácticas', 'practicante'])

def preprocess_text(text):
    if not text: return ""
    text = text.lower()
    try:
        tokens = word_tokenize(text, language='spanish')
    except LookupError:
        try:
            nltk.download('punkt', quiet=True)
            tokens = word_tokenize(text, language='spanish')
        except Exception as e:
            tokens = text.split()
    table = str.maketrans('', '', string.punctuation)
    stripped = [w.translate(table) for w in tokens]
    words = [word for word in stripped if word.isalpha() and word not in stop_words_es and len(word) > 2]
    return " ".join(words)

class ContentBasedRecommender:
    def __init__(self):
        self.vectorizer = TfidfVectorizer(preprocessor=preprocess_text, ngram_range=(1,2))
        self.ofertas_df = []
        self.ofertas_matrix = None
        self.fitted = False

    def fit(self, ofertas_data):
        if not ofertas_data:
            print("ML_DEBUG: No hay datos de ofertas para entrenar el recomendador.")
            self.fitted = False
            return
        self.ofertas_df = ofertas_data
        # print(f"ML_DEBUG: Preparando contenido de {len(ofertas_data)} ofertas para TF-IDF.")
        ofertas_content_for_tfidf = [
            f"{oferta.get('titulo_oferta', '')} {oferta.get('descripcion_completa_oferta', '')}"
            for oferta in ofertas_data
        ]
        try:
            self.ofertas_matrix = self.vectorizer.fit_transform(ofertas_content_for_tfidf)
            self.fitted = True
            print(f"ML_DEBUG: Recomendador entrenado/actualizado. Matriz TF-IDF: {self.ofertas_matrix.shape}")
        except ValueError as e:
            print(f"ML_DEBUG ERROR: al entrenar el vectorizador: {e}.")
            self.fitted = False

    def recommend(self, perfil_egresado, top_n=5):
        if not self.fitted:
            print("ML_DEBUG: Recomendador no entrenado.")
            return []
        if not perfil_egresado:
            print("ML_DEBUG: Perfil de egresado vacío en recommend().")
            return []
        perfil_content_list = [
            str(perfil_egresado.get('habilidades_texto', '')),
            str(perfil_egresado.get('experiencia_texto', '')),
            str(perfil_egresado.get('preferencias_texto', '')),
            str(perfil_egresado.get('formacion_texto', ''))
        ]
        perfil_content = " ".join(filter(None, perfil_content_list))
        # print(f"ML_DEBUG: Contenido del perfil para recomendación: '{perfil_content[:100]}...'")
        if not perfil_content.strip():
            print("ML_DEBUG: Contenido del perfil procesado está vacío.")
            return []
        try:
            perfil_vector = self.vectorizer.transform([perfil_content])
        except ValueError as e:
            print(f"ML_DEBUG ERROR: al transformar el perfil: {e}")
            return []
        if self.ofertas_matrix is None or self.ofertas_matrix.shape[0] == 0:
            print("ML_DEBUG: Matriz de ofertas vacía en recommend().")
            return []
        cosine_similarities = cosine_similarity(perfil_vector, self.ofertas_matrix)
        # print(f"ML_DEBUG: Scores de similitud (primeros 5): {cosine_similarities[0][:5]}")
        if cosine_similarities.size == 0: return []
        similar_indices_sorted = cosine_similarities[0].argsort()[::-1]
        recommendations = []
        for i in similar_indices_sorted:
            if len(recommendations) < top_n:
                score = cosine_similarities[0][i]
                if score > 0.02: # Umbral
                    oferta_completa_recomendada = dict(self.ofertas_df[i])
                    oferta_completa_recomendada['score_similitud'] = score
                    recommendations.append(oferta_completa_recomendada)
            else: break
        # print(f"ML_DEBUG: Total recomendaciones finales: {len(recommendations)}")
        return recommendations

def cargar_ofertas_activas_db():
    ofertas = db.query_db(
        "SELECT id_oferta, titulo_oferta, empresa_nombre, ubicacion, descripcion_completa_oferta, fecha_publicacion "
        "FROM OfertasLaborales WHERE activa = TRUE"
    )
    return ofertas if ofertas else []

def cargar_perfil_usuario_db(id_usuario):
    perfil = db.query_db(
        "SELECT id_usuario, habilidades_texto, experiencia_texto, preferencias_texto, formacion_texto "
        "FROM PerfilesEgresados WHERE id_usuario = %s", (id_usuario,), one=True
    )
    return perfil

recommender_instance = ContentBasedRecommender()

def inicializar_y_entrenar_recomendador():
    print("ML_DEBUG: Inicializando y/o entrenando el recomendador...")
    ofertas_data = cargar_ofertas_activas_db()
    if ofertas_data:
        recommender_instance.fit(ofertas_data)
    else:
        print("ML_DEBUG: No se encontraron ofertas activas para entrenar el recomendador.")

if __name__ == '__main__':
    pass