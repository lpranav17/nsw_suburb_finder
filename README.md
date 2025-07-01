# Sydney Suburb Analyzer 🏠

A comprehensive tool to analyze and rank Sydney suburbs based on Points of Interest (POI) data from NSW government open data sources. The system provides personalized suburb recommendations based on user preferences for recreation, community, transport, education, and utility facilities.

## 🎯 Project Overview

This project helps users find the best suburb to live in Sydney by analyzing POI data from NSW government datasets and providing an interactive web application to customize their preferences. The system focuses on Greater Sydney SA4 regions and provides data-driven recommendations.

## 📊 Data Sources

### NSW Government Open Data
- **NSW POI (Points of Interest) API**: Comprehensive POI data including recreation, community, transport, education, and utility facilities
- **API Endpoint**: https://maps.six.nsw.gov.au/arcgis/rest/services/public/NSW_POI/MapServer/0/query
- **Coverage**: Greater Sydney SA4 regions

### POI Categories
- **Recreation**: Parks, sports facilities, beaches, entertainment venues
- **Community**: Community centers, libraries, cultural facilities
- **Transport**: Public transport, stations, accessibility
- **Education**: Schools, universities, educational facilities
- **Utility**: Essential services, utilities, infrastructure

## 🏗️ Project Structure

```
Sample1/
├── config/
│   └── config.yaml          # Database and API configuration
├── src/
│   ├── data/
│   │   └── collectors/      # Data collection modules
│   └── analysis/
│       └── scoring_engine.py # Suburb scoring algorithms
├── web_app/
│   ├── app.py              # FastAPI web application
│   ├── requirements.txt    # Python dependencies
│   └── start.py           # Application startup script
├── main.py                 # Main data collection script
├── create_web_app.py       # Web app creation script
├── requirements.txt        # Project dependencies
└── README.md              # Project documentation
```

## 🚀 Features

### Core Functionality
- **SA4 Region Analysis**: Focus on Greater Sydney SA4 statistical areas
- **POI-based Scoring**: Analyze suburbs based on Points of Interest density
- **Customizable Weighting**: Users can adjust importance of different POI categories
- **Interactive Web Interface**: Modern, responsive web application
- **Real-time Recommendations**: Instant suburb recommendations based on preferences
- **Comprehensive Data**: 8,000+ POIs across 12 SA4 regions

### SA4 Regions Covered
- Sydney - City and Inner South
- Sydney - Eastern Suburbs
- Sydney - Inner South West
- Sydney - Inner West
- Sydney - North Sydney and Hornsby
- Sydney - Northern Beaches
- Sydney - Outer South West
- Sydney - Outer West and Blue Mountains
- Sydney - Parramatta
- Sydney - Ryde
- Sydney - South West
- Sydney - Sutherland

## 🛠️ Technology Stack

### Backend
- **Python 3.12**: Data processing and analysis
- **FastAPI**: Modern REST API framework
- **SQLAlchemy**: Database ORM
- **PostgreSQL**: Data storage with PostGIS extension
- **Pandas**: Data manipulation and analysis
- **Requests**: HTTP client for NSW APIs

### Database
- **PostgreSQL**: Primary database
- **PostGIS**: Spatial data support
- **Spatial Indexing**: Optimized POI queries

### Web Application
- **FastAPI**: Backend API
- **HTML/CSS/JavaScript**: Frontend interface
- **Uvicorn**: ASGI server

## 📊 Data Collection

### Current Implementation
- **8,669 unique POIs** collected from NSW API
- **12 SA4 regions** covered in Greater Sydney
- **5 POI categories** analyzed
- **Spatial data** with latitude/longitude coordinates

### POI Distribution
- **Recreation**: 4,891 POIs (56.4%)
- **Community**: 2,405 POIs (27.7%)
- **Transport**: 644 POIs (7.4%)
- **Education**: 261 POIs (3.0%)
- **Utility**: 49 POIs (0.6%)
- **Other**: 419 POIs (4.9%)

## 🚀 Getting Started

### Prerequisites
- Python 3.12+
- PostgreSQL 12+ with PostGIS extension
- Git

### Installation

1. **Clone and setup:**
   ```bash
   git clone <repository-url>
   cd Sample1
   pip install -r requirements.txt
   ```

2. **Configure database:**
   ```bash
   # Edit config/config.yaml with your PostgreSQL credentials
   # Example:
   database:
     host: localhost
     port: 5432
     name: sydney_analyzer
     user: your_username
     password: your_password
   ```

3. **Collect POI data:**
   ```bash
   python main.py
   ```
   This will collect 8,669 POIs from NSW API and store them in PostgreSQL.

4. **Create web application:**
   ```bash
   python create_web_app.py
   ```

5. **Start the web app:**
   ```bash
   cd web_app
   pip install -r requirements.txt
   python start.py
   ```

6. **Access the application:**
   - Open your browser to: http://localhost:8000
   - API documentation: http://localhost:8000/docs

## 🎯 How It Works

### Data Collection Process
1. **API Queries**: Multiple bounding box queries to NSW POI API
2. **Deduplication**: Remove duplicate POIs across regions
3. **Categorization**: Map POI types to categories (Recreation, Community, etc.)
4. **Spatial Storage**: Store with PostGIS geometry for spatial queries

### Recommendation Algorithm
1. **User Preferences**: Collect weights for each POI category
2. **POI Counting**: Count POIs by category for each SA4 region
3. **Normalization**: Scale counts relative to maximum in dataset
4. **Weighted Scoring**: Calculate weighted score based on preferences
5. **Ranking**: Sort regions by score and return top recommendations

### Web Interface
- **Interactive Sliders**: Adjust preference weights (0-100%)
- **Real-time Updates**: Instant recommendations as preferences change
- **Detailed Breakdown**: Show POI counts for each category
- **Responsive Design**: Works on desktop and mobile

## 📈 API Endpoints

### Web Interface
- `GET /`: Main web interface
- `POST /api/recommendations`: Get suburb recommendations
- `GET /api/stats`: Get overall statistics

### Request Format
```json
{
  "recreation": 0.25,
  "community": 0.25,
  "transport": 0.25,
  "education": 0.15,
  "utility": 0.10
}
```

### Response Format
```json
[
  {
    "suburb_name": "Sydney - Eastern Suburbs",
    "score": 0.85,
    "poi_counts": {
      "recreation": 450,
      "community": 280,
      "transport": 120,
      "education": 45,
      "utility": 15
    },
    "total_pois": 910,
    "latitude": -33.89,
    "longitude": 151.25
  }
]
```

## 🔧 Configuration

### Database Configuration
Edit `config/config.yaml`:
```yaml
database:
  host: localhost
  port: 5432
  name: sydney_analyzer
  user: your_username
  password: your_password
```

### API Configuration
The NSW POI API is public and doesn't require authentication.

## 📊 Data Quality

### Validation
- **Duplicate Detection**: Automatic removal of duplicate POIs
- **Coordinate Validation**: Ensure valid latitude/longitude
- **Category Mapping**: Consistent POI type categorization

### Coverage
- **Geographic**: All major SA4 regions in Greater Sydney
- **Temporal**: Current data from NSW government
- **Completeness**: 8,669 unique POIs with full metadata

## 🚀 Future Enhancements

### Planned Features
- **Additional Data Sources**: Property prices, crime rates, school performance
- **Advanced Analytics**: Trend analysis, predictive modeling
- **Interactive Maps**: Visual representation of POI data
- **User Accounts**: Save preferences and search history
- **Mobile App**: Native mobile application

### Data Expansion
- **More POI Categories**: Healthcare, shopping, entertainment
- **Historical Data**: Track changes over time
- **Real-time Updates**: Automated data refresh
- **External APIs**: Integration with real estate and transport APIs

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- NSW Government for providing open POI data
- Six Maps NSW for the comprehensive POI API
- PostgreSQL and PostGIS communities
- FastAPI and Python communities

## 📞 Support

For questions or support, please open an issue on GitHub or contact the development team.

## 📊 Current Status

✅ **Completed:**
- POI data collection from NSW API
- Database setup with PostgreSQL/PostGIS
- SA4 region analysis
- Web application with FastAPI
- Interactive preference-based recommendations
- 8,669 POIs across 12 SA4 regions

🔄 **In Progress:**
- Additional data source integration
- Advanced analytics features
- Performance optimization

📋 **Planned:**
- Interactive maps
- Mobile application
- Real-time data updates
- User account system 