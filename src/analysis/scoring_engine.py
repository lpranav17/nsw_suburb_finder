import math
import logging
from typing import Dict, List, Optional, Any
from sqlalchemy import create_engine, text
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

class WellResourcedScoringEngine:
    """Engine for calculating well-resourced scores for SA2 regions"""
    
    def __init__(self, db_engine):
        """Initialize the scoring engine with database connection"""
        self.db_engine = db_engine
    
    def calculate_well_resourced_score(self, sa4_codes: List[str] = None) -> Dict[str, Any]:
        """
        Calculate well-resourced score for each SA2 region using the formula:
        Score = S(zbusiness + zstops + zschools + zPOI)
        where S is the sigmoid function
        """
        if sa4_codes is None:
            sa4_codes = ['117', '125', '126']  # Sydney City, Parramatta, Ryde
        
        try:
            # 1. Get all SA2 regions
            sa2_regions = self._get_sa2_regions(sa4_codes)
            logger.info(f"Found {len(sa2_regions)} SA2 regions")
            
            # 2. Calculate each component for all SA2s
            all_scores = []
            for sa2_code, sa2_name in sa2_regions:
                scores = self._calculate_component_scores(sa2_code, sa2_name)
                all_scores.append(scores)
            
            # 3. Calculate z-scores for each component
            all_scores = self._calculate_z_scores(all_scores)
            
            # 4. Calculate final score using sigmoid
            all_scores = self._calculate_final_scores(all_scores)
            
            # 5. Store results in database
            self._store_scores_in_database(all_scores)
            
            # 6. Return summary
            return self._generate_summary(all_scores)
            
        except Exception as e:
            logger.error(f"Error calculating well-resourced scores: {e}")
            raise
    
    def _get_sa2_regions(self, sa4_codes: List[str]) -> List[tuple]:
        """Get SA2 regions from database"""
        query = """
            SELECT DISTINCT sa2_code, sa2_name
            FROM businesses
            WHERE substring(sa2_code from 1 for 3) = ANY(%s)
        """
        
        with self.db_engine.connect() as conn:
            result = conn.execute(text(query), sa4_codes)
            return [(row[0], row[1]) for row in result]
    
    def _calculate_component_scores(self, sa2_code: str, sa2_name: str) -> Dict[str, Any]:
        """Calculate raw scores for each component"""
        scores = {
            'sa2_code': sa2_code,
            'sa2_name': sa2_name,
            'raw_scores': {}
        }
        
        # Business score (zbusiness) - Updated with 7 selected industries
        business_score = self._calculate_business_score(sa2_code)
        scores['raw_scores']['business'] = business_score
        
        # Transport stops score (zstops)
        stops_score = self._calculate_stops_score(sa2_code)
        scores['raw_scores']['stops'] = stops_score
        
        # Schools score (zschools)
        schools_score = self._calculate_schools_score(sa2_code)
        scores['raw_scores']['schools'] = schools_score
        
        # POI score (zPOI)
        poi_score = self._calculate_poi_score(sa2_code)
        scores['raw_scores']['poi'] = poi_score
        
        return scores
    
    def _calculate_business_score(self, sa2_code: str) -> int:
        """Calculate business score based on relevant industries"""
        query = """
            SELECT 
                SUM(total_businesses) as total_businesses,
                SUM(CASE 
                    WHEN industry_name IN (
                        'Health Care and Social Assistance',
                        'Rental, Hiring and Real Estate Services',
                        'Transport, Postal and Warehousing',
                        'Electricity, Gas, Water and Waste Services',
                        'Financial and Insurance Services',
                        'Accomodation and Food Services',
                        'Education and Training'
                    ) 
                    THEN total_businesses 
                    ELSE 0 
                END) as relevant_businesses
            FROM businesses
            WHERE sa2_code = %s
        """
        
        with self.db_engine.connect() as conn:
            result = conn.execute(text(query), sa2_code)
            row = result.fetchone()
            return row[1] if row and row[1] else 0
    
    def _calculate_stops_score(self, sa2_code: str) -> int:
        """Calculate transport stops score"""
        query = """
            SELECT COUNT(*) as stop_count
            FROM stops s
            JOIN sa2_boundaries b ON ST_Contains(b.geometry, s.geom)
            WHERE b.sa2_code = %s
        """
        
        with self.db_engine.connect() as conn:
            result = conn.execute(text(query), sa2_code)
            row = result.fetchone()
            return row[0] if row else 0
    
    def _calculate_schools_score(self, sa2_code: str) -> int:
        """Calculate schools score based on student capacity"""
        query = """
            SELECT 
                SUM(kindergart + year1 + year2 + year3 + year4 + year5 + 
                    year6 + year7 + year8 + year9 + year10 + year11 + year12) as total_students
            FROM schools s
            JOIN sa2_boundaries b ON ST_Contains(b.geometry, s.geom)
            WHERE b.sa2_code = %s
        """
        
        with self.db_engine.connect() as conn:
            result = conn.execute(text(query), sa2_code)
            row = result.fetchone()
            return row[0] if row and row[0] else 0
    
    def _calculate_poi_score(self, sa2_code: str) -> int:
        """Calculate POI score"""
        query = """
            SELECT COUNT(*) as poi_count
            FROM poi_data p
            JOIN sa2_boundaries b ON ST_Contains(
                b.geometry, 
                p.geom
            )
            WHERE b.sa2_code = %s
        """
        
        with self.db_engine.connect() as conn:
            result = conn.execute(text(query), sa2_code)
            row = result.fetchone()
            return row[0] if row else 0
    
    def _calculate_z_scores(self, all_scores: List[Dict]) -> List[Dict]:
        """Calculate z-scores for each component"""
        for component in ['business', 'stops', 'schools', 'poi']:
            values = [s['raw_scores'][component] for s in all_scores]
            mean = sum(values) / len(values)
            std = (sum((x - mean) ** 2 for x in values) / len(values)) ** 0.5
            
            for score in all_scores:
                z_score = (score['raw_scores'][component] - mean) / std if std != 0 else 0
                score['z_scores'] = score.get('z_scores', {})
                score['z_scores'][component] = z_score
        
        return all_scores
    
    def _calculate_final_scores(self, all_scores: List[Dict]) -> List[Dict]:
        """Calculate final score using sigmoid function"""
        for score in all_scores:
            total_z = sum(score['z_scores'].values())
            score['final_score'] = 1 / (1 + math.exp(-total_z))
        
        return all_scores
    
    def _store_scores_in_database(self, all_scores: List[Dict]):
        """Store scoring results in database"""
        # Create table if not exists
        create_table_query = """
            CREATE TABLE IF NOT EXISTS sa2_scores (
                sa2_code VARCHAR(10),
                sa2_name VARCHAR(100),
                business_score FLOAT,
                stops_score FLOAT,
                schools_score FLOAT,
                poi_score FLOAT,
                total_score FLOAT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """
        
        with self.db_engine.connect() as conn:
            conn.execute(text(create_table_query))
            
            # Clear existing data
            conn.execute(text("DELETE FROM sa2_scores"))
            
            # Insert new scores
            for score in all_scores:
                insert_query = """
                    INSERT INTO sa2_scores 
                    (sa2_code, sa2_name, business_score, stops_score, 
                     schools_score, poi_score, total_score)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """
                conn.execute(text(insert_query), (
                    score['sa2_code'],
                    score['sa2_name'],
                    score['z_scores']['business'],
                    score['z_scores']['stops'],
                    score['z_scores']['schools'],
                    score['z_scores']['poi'],
                    score['final_score']
                ))
            
            conn.commit()
            logger.info(f"Stored {len(all_scores)} scoring results in database")
    
    def _generate_summary(self, all_scores: List[Dict]) -> Dict[str, Any]:
        """Generate summary statistics"""
        sorted_scores = sorted(all_scores, key=lambda x: x['final_score'], reverse=True)
        
        summary = {
            'total_regions': len(all_scores),
            'top_5_regions': [
                {
                    'name': score['sa2_name'],
                    'score': round(score['final_score'], 3)
                }
                for score in sorted_scores[:5]
            ],
            'bottom_5_regions': [
                {
                    'name': score['sa2_name'],
                    'score': round(score['final_score'], 3)
                }
                for score in sorted_scores[-5:]
            ],
            'score_statistics': {
                'mean': np.mean([s['final_score'] for s in all_scores]),
                'median': np.median([s['final_score'] for s in all_scores]),
                'std': np.std([s['final_score'] for s in all_scores]),
                'min': min([s['final_score'] for s in all_scores]),
                'max': max([s['final_score'] for s in all_scores])
            }
        }
        
        return summary
    
    def get_scores_for_visualization(self) -> pd.DataFrame:
        """Get scores for visualization purposes"""
        query = """
            SELECT 
                b.geometry,
                s.sa2_code,
                s.sa2_name,
                s.total_score,
                s.business_score,
                s.stops_score,
                s.schools_score,
                s.poi_score
            FROM sa2_boundaries b
            JOIN sa2_scores s ON b.sa2_code = s.sa2_code
        """
        
        with self.db_engine.connect() as conn:
            return pd.read_sql(query, conn)
    
    def get_score_correlation_with_income(self) -> Dict[str, float]:
        """Calculate correlation between well-resourced score and median income"""
        query = """
            SELECT 
                s.total_score,
                i.median_income
            FROM sa2_scores s
            JOIN income i ON s.sa2_code = i.sa2_code
            WHERE i.median_income IS NOT NULL AND i.median_income > 0
        """
        
        with self.db_engine.connect() as conn:
            df = pd.read_sql(query, conn)
            
            if len(df) > 0:
                correlation = df['total_score'].corr(df['median_income'], method='pearson')
                return {
                    'correlation': correlation,
                    'sample_size': len(df)
                }
            else:
                return {
                    'correlation': None,
                    'sample_size': 0
                }
    
    def get_component_breakdown(self, sa2_code: str) -> Dict[str, Any]:
        """Get detailed component breakdown for a specific SA2 region"""
        query = """
            SELECT 
                sa2_code,
                sa2_name,
                business_score,
                stops_score,
                schools_score,
                poi_score,
                total_score
            FROM sa2_scores
            WHERE sa2_code = %s
        """
        
        with self.db_engine.connect() as conn:
            result = conn.execute(text(query), sa2_code)
            row = result.fetchone()
            
            if row:
                return {
                    'sa2_code': row[0],
                    'sa2_name': row[1],
                    'components': {
                        'business': row[2],
                        'transport': row[3],
                        'education': row[4],
                        'amenities': row[5]
                    },
                    'total_score': row[6]
                }
            else:
                return None 