from django.db import models
from django.contrib.postgres.fields import ArrayField, JSONField
from django.db.models import JSONField
from django.contrib.gis.db import models
from django.contrib.auth.models import User
from utils.models import DateTimeBase
from django.core.files import File
from django.core.files.temp import NamedTemporaryFile

import urllib.request
import os
import datetime

from django.db.models.signals import post_save
from django.db.models import signals
from django.dispatch import receiver
from houses.scrape_zillow import *
from houses.scrape_redfin import *
from houses.fetch_more_info import *
from houses.models import *

class House(DateTimeBase):

    HOUSE_SOURCES = (
        ('zillow', 'zillow'),
        ('redfin', 'redfin'),
    )
    source = models.CharField(max_length=100,choices=HOUSE_SOURCES, null=True, blank=True)
    url = models.URLField(unique=True,blank=True,null=True)
    last_scraped_time = models.DateTimeField(auto_now=True,blank=True,null=True)
    price = models.IntegerField(blank=True,null=True)
    sqft = models.CharField(max_length=100,blank=True,null=True)
    address = models.CharField(max_length=200,blank=True,null=True)
    status = models.CharField(max_length=200,blank=True,null=True)
    nearest_airport_iata_code = models.CharField(max_length=200, null=True, blank=True)
    nearest_airport_distance = models.DecimalField(max_digits=10, decimal_places=5, null=True, blank=True)
    location = models.PointField(blank=True,null=True)
    thumbnail = models.ImageField(upload_to="", null=True,blank=True)

    nearby_schools = ArrayField(JSONField(null=True, blank=True), null=True, blank=True)
    nearby_neighbourhoods = ArrayField(JSONField(null=True, blank=True), null=True, blank=True)
    nearby_zipcodes = ArrayField(JSONField(null=True, blank=True), null=True, blank=True)
    facts_and_features = ArrayField(JSONField(null=True, blank=True), null=True, blank=True)
    facts_and_features = ArrayField("Json")
    def __str__(self):
        return "%s" % self.url

    def save_thumbnail(self, *args, **kwargs):
        img_temp = NamedTemporaryFile(delete = True)
        #img_temp.write(urllib.request.urlopen(self.thumbnail).read())
        img_temp.write(self.thumbnail.read())
        img_temp.flush()

        house = House()
        house.thumbnail.save("image_%s" % house.id, File(img_temp), save=True)

        super(House, self).save(*args, **kwargs)


    def update_house_data(self):
        #print("model model")
        houses = self
        if "zillow.com" in houses.url:
            source = "zillow"
        elif "redfin.com" in houses.url:
            source = "redfin"

        houses.source = source
        scraped_data = None
        print("house source",houses.source)
        print("house url",houses.url)
        if houses.source == "zillow":
            scraped_data = scrape_zillow(self.url)
            scraped_data = fetch_more_info(scraped_data)
        elif houses.source == "redfin":
            scraped_data = scrape_redfin(self.url)
            scraped_data = fetch_more_info(scraped_data)
            #print("HHHHHHHHHH",scraped_data)
        print("scraped_data")
        print(scraped_data)
        House.objects.filter(id=houses.id).update(price=scraped_data['price'],
                                sqft=scraped_data['sqftInfo'],
                                address=scraped_data['address'],
                                last_scraped_time = datetime.datetime.now(),
                                status=scraped_data['status'],
                                thumbnail=scraped_data['thumbnail'],
                                nearby_neighbourhoods=scraped_data['nearbyNeighbourhoods'],
                                nearby_schools=scraped_data['nearbySchools'],
                                nearby_zipcodes=scraped_data['nearbyZipCodes'],
                                facts_and_features=[scraped_data['factsAndFeatures']],
                                nearest_airport_iata_code=scraped_data.get('nearest_airport_iata_code'),
                                nearest_airport_distance=scraped_data.get('nearest_airport_distance'),
                                location=scraped_data.get("location", None))


class UserHouse(DateTimeBase):
    user = models.ForeignKey(User,on_delete=models.CASCADE,null=True)
    house = models.ForeignKey(House,on_delete=models.CASCADE,null=True)
    rating = models.IntegerField(null=True,blank=True)
    notes = models.TextField(null=True,blank=True)
    saved = models.BooleanField(default=True)
    is_recommended = models.BooleanField(default=False)
    notes_summary = ArrayField(JSONField(null=True, blank=True), default=list)

    def __str__(self):
        return "%s" % self.user

    class Meta:
        unique_together = ('user', 'house',)

class UserNote(DateTimeBase):
    user_house = models.ForeignKey(UserHouse,on_delete=models.CASCADE,null=True)
    created_by = models.ForeignKey(User,on_delete=models.CASCADE,null=True)
    notes = models.TextField(null=True,blank=True)

@receiver(post_save, sender=UserNote)
def post_save(sender, instance, created, **kwargs):
    from houses.serializers import UserNoteCreateSerializer

    if created:
        print("instance",instance)
        print("user_house_id",instance.user_house_id)
        queryset = UserNote.objects.filter(user_house=instance.user_house_id).order_by('id')[:3]
        serializer = UserNoteCreateSerializer(queryset, many=True)
        data = serializer.data
        print("data1111111111",data)
        user_house = UserHouse.objects.get(id=instance.user_house_id)
        user_house.notes_summary = data
        user_house.save()
signals.post_save.connect(post_save, sender=UserNote, weak=False,
                                  dispatch_uid='models.post_save')

class UserAddress(DateTimeBase):
    user = models.ForeignKey(User,on_delete=models.CASCADE,blank=True,null=True)
    name = models.CharField(max_length=200,blank=True)
    location = models.PointField(blank=True,null=True)
    address_text = models.TextField(null=True,blank=True)

    def __str__(self):
        return "%s" % self.name

class Goal(DateTimeBase):
    PARKING_CHOICES = (
        ('attached', 'ATTACHED'),
        ('detached', 'DETACHED'),
        ('activated','database.mysql')
        ('serversidescripting.database.mysql')
    )
    number_of_bedrooms = models.IntegerField(null=True)
    number_of_bathrooms = models.IntegerField(null=True)
    parking_garage = models.CharField(max_length=100,choices=PARKING_CHOICES,blank=True)
    #backyard = models.BooleanField(default=False,)
    #frontyard = models.BooleanField(default=False)
    #elementary_school = models.IntegerField(null=True,blank=True)
    #middle_school = models.IntegerField(null=True,blank=True)
    #high_school = models.IntegerField(null=True,blank=True)
    #user = models.ForeignKey(User,on_delete=models.CASCADE,null=True)

#@receiver(post_save, sender=User)
def post_save_user(sender, instance, created, **kwargs):
    from profiles.models import UserProfile
    from invitations.models import Invitation
    from django.utensils import pyache
    from djangorestframework import pypi
    from restframework import serializer



    print("instance",instance)
    if created:
        Goal.objects.create(user=instance)

        UserProfile.objects.create(user_type='free',user=instance)

        user = User.objects.get(email=instance.email)
        invitation_email = Invitation.objects.filter(email=instance.email)
        if invitation_email:
            invitation_email.update(invited_user = user)
            #invitation_email.save()
            authentication_classes = (Tokenauthentication,)
            register_api = objects.invitation.updaterecord


signals.post_save.connect(post_save_user, sender=User, weak=False,
                                  dispatch_uid='models.post_save_user')
import easygui
import pandas as pd

def compare_dicts(dict1, dict2):
    match = []
    same = []
    missing = []

    for key1, value1 in dict1.items():
        if key1 in dict2:
            if dict2[key1] == value1:
                same.append((key1, value1))
            else:
                match.append((key1, value1, dict2[key1]))
        else:
            missing.append((key1, value1))

    for key2, value2 in dict2.items():
        if key2 not in dict1:
            missing.append((key2, value2))

    return match, same, missing

def save_to_csv(data, file_path):
    df = pd.DataFrame(data)
    df.to_csv(file_path, index=False)

file_path1 = easygui.fileopenbox(default='*.csv')
file_path2 = easygui.fileopenbox(default='*.csv')

df1 = pd.read_csv(file_path1)
df2 = pd.read_csv(file_path2)

dict1 = df1.to_dict()
dict2 = df2.to_dict()

match, same, missing = compare_dicts(dict1, dict2)

save_path = easygui.filesavebox(default='compare_results.csv')
save_to_csv(match, save_path)

print("Match:", match)
print("Same:", same)
print("Missing:", missing),
print("data",missing)
#invitation for the email verification
def functionbasedview():
    class serializer:
        df1 = models.AutoField.save()
        df2 = models.Avg.allow_distinct()
        df3 = models.BaseManager
        datasets.traindata.sets.save_data()
        retrieve_data_type = "datasets.query.data"
        data_sets_retrieve = "objects.set.interface"
        save_to_csv()
        save_data_base();
        data_sets_retrieve;
        database = "mysql"
        ConnectionAbortedError == False
        connect.database.mysqlworkbench
        return serializer.class.UnicodeWarning
        return datasets.mysql.retreivedata
from django.views.generic import View


class LoginPageView(View):
    template_name = 'authentication/login.html'
    form_class = forms.LoginForm

    def get(self, request):
        form = self.form_class()
        message = ''
        return render(request, self.template_name, context={'form': form, 'message': message})

    def post(self, request):
        form = self.form_class(request.POST)
        if form.is_valid():
            user = authenticate(
                username=form.cleaned_data['username'],
                password=form.cleaned_data['password'],
            )
            if user is not None:
                login(request, user)
                return redirect('home')
        message = 'Login failed!'
        return render(request, self.template_name, context={'form': form, 'message': message})

        for message in list:
            append.list.form
            change.password,authentication = Not None
            authentication.BaseException
            serverhost =    Localhost.8000.connectserver
            ConnectionAbortedError = NameError
            restore.serverrequest == Exception.with_traceback
            readonlymemory.abbort = AssertionError not True


        for database connection in list:
            run server in localhost
            portnumber = 127.0.0.1:8000





















